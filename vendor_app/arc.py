"""ARC & FO master: contracts, the frame orders under them, and their items.

Two inputs, at line-item granularity, exactly as the reports produce them:

    Table 1  ARC data (ME3L)          one row per ITEM of a purchasing document
    Table 2  Framework tracking       one row per ITEM of a frame order

    Purchasing Document  (the contract, the key everything is filed against)
     |  header facts repeat on every item: vendor, validity, target value,
     |  release indicator and status
     +-- Item                     Table 1: what the contract covers
     +-- Frame Number  (FO)       Table 2: an order placed against the contract
          +-- Item                Table 2: what that order released

The one rule everything else follows: **a repeated header value is read
once per document, never summed across its duplicates.** Target Val.
(Header) appears on every item of a contract; adding those up would report
a contract worth five times what it is. Per-item money - Released, Actual
and Opening Value - does add up within its frame order, because those
figures belong to the item, not to the header.

Every roll-up is derived on read and never stored, so no total can drift
out of step with the rows it came from.
"""

import os
import re
import threading
from collections import OrderedDict
from datetime import date, datetime

import pandas as pd

from vendor_app.config import (
    ARC_DATE_FIELDS,
    ARC_FILE,
    ARC_HEADER_KEYS,
    ARC_KEYS,
    ARC_KEY_FIELDS,
    ARC_LABELS,
    ARC_LEGACY_COLUMNS,
    DATA_DIR,
    FO_DATE_FIELDS,
    FO_FILE,
    FO_ITEM_VALUE_KEYS,
    FO_KEYS,
    FO_KEY_FIELDS,
    FO_LABELS,
    FO_LEGACY_COLUMNS,
)
from vendor_app.validators import ValidationError, normalize

_NUMBER_RE = re.compile(r"[^0-9.\-]")
_TRAILING_ZEROS_RE = re.compile(r"^(\d+)\.0+$")
_VENDOR_RE = re.compile(r"^(\d+)\s*[-/:.]?\s*(.*)$")


def parse_amount(value) -> float:
    """Read a money cell leniently.

    Figures arrive pasted out of Excel, so '1,20,000', '₹ 45000.50' and
    '45000' all have to add up to the same thing. Anything unreadable
    counts as zero rather than blowing up a roll-up over thousands of rows.
    """
    text = normalize(value)
    if not text:
        return 0.0
    cleaned = _NUMBER_RE.sub("", text)
    if cleaned in ("", "-", ".", "-."):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def format_amount(value: float) -> str:
    """Render a rolled-up figure with thousands separators, no trailing .0."""
    if not value:
        return "0"
    if abs(value - round(value)) < 0.005:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def display_amount(text) -> str:
    """A money cell tidied with thousands separators for the grid.

    Only when the cell is plainly a number. Anything carrying letters - a
    note, a unit, "1.5 Cr" - is shown exactly as it was typed, because
    rewriting it would turn a figure into something it may not mean. The
    stored value is never changed by this; it is a display pass only.
    """
    raw = normalize(text)
    if not raw or any(ch.isalpha() for ch in raw):
        return raw
    value = parse_amount(raw)
    return format_amount(value) if value else raw


def document_key(value) -> str:
    """The comparison form of a document, frame or item number.

    A contract number is the join between the two files, and the two files
    do not always write it identically. The same purchasing document arrives
    as 4600001201 from one export and, when the column was numeric and the
    sheet was read by a spreadsheet, as "4600001201.0"; as " 4600001201 "
    with padding; as "'4600001201" with Excel's text marker; as
    "4,600,001,201" once a thousands separator has been applied; and as
    "0004600001201" wherever SAP has zero-padded it. Item numbers show the
    same split between "10" and "00010".

    Comparing the raw text means a contract that plainly HAS frame orders is
    reported as having none, which is the one answer this module must never
    get wrong. So every identity comparison goes through this: padding,
    markers, separators and a numeric column's trailing ".0" are removed, a
    purely numeric key is compared without its leading zeros, and anything
    else is compared case-insensitively.

    It only ever normalises the FORM of a number. Two genuinely different
    numbers can never collide here, because nothing but formatting is
    stripped.
    """
    text = normalize(value).replace("\u00a0", " ").strip().lstrip("'").strip()
    if not text:
        return ""
    text = text.replace(" ", "")
    match = _TRAILING_ZEROS_RE.match(text)
    if match:
        text = match.group(1)
    unseparated = text.replace(",", "")
    if unseparated.isdigit():
        return unseparated.lstrip("0") or "0"
    return text.casefold()


def split_vendor(text):
    """'100234 Vendor Name' -> ('100234', 'Vendor Name').

    Table 1 carries the code and the name in one column. They are split for
    the vendor master and the vendor-wise analysis, while the column itself
    keeps the text exactly as the export wrote it.
    """
    raw = normalize(text)
    if not raw:
        return ("", "")
    match = _VENDOR_RE.match(raw)
    if match:
        return (match.group(1), match.group(2).strip())
    return ("", raw)


# Dates arrive as DD.MM.YYYY from SAP and in whatever shape a person types.
# The SAP format leads because that is what an untouched download contains.
DATE_FORMATS = (
    "%d.%m.%Y", "%d.%m.%y",
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
    "%d-%b-%Y", "%d %b %Y", "%b %d %Y", "%d %B %Y",
    "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
)

# Every ARC and FO date is shown in exactly this shape, whatever it arrived as.
DATE_DISPLAY_FORMAT = "%d.%m.%Y"

# A real date cell read out of Excel comes through pandas as
# "2026-09-16 00:00:00" - the midnight is an artefact of the cell's type, not
# information. It is stripped before parsing so it can never reach the screen.
_TIME_TAIL_RE = re.compile(r"[ T]\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*(AM|PM|am|pm)?$")


def parse_date(value):
    """Read a validity date leniently. Returns a date, or None if unreadable.

    An unreadable date must never be guessed at: it is reported as "no date"
    and counted separately, because silently treating it as expired - or as
    active - would put a wrong contract in front of management.
    """
    text = _TIME_TAIL_RE.sub("", normalize(value)).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_date(value) -> str:
    """A date rendered as DD.MM.YYYY - the only shape ARC and FO dates take.

    A cell that cannot be read as a date is returned exactly as it was
    written. Reformatting something that is not a date would replace what
    somebody typed with a guess, and a note in a date column ("TBD", "on
    award") has to survive being looked at.
    """
    parsed = parse_date(value)
    return parsed.strftime(DATE_DISPLAY_FORMAT) if parsed else normalize(value)


def days_until(value, today=None):
    """Days from `today` to `value`; negative once it has passed.

    None when the date cannot be read, so callers can keep those rows out of
    the expiry buckets instead of bucketing them wrongly.
    """
    end = parse_date(value)
    if end is None:
        return None
    return (end - (today or date.today())).days


def _clean(raw: dict, keys) -> dict:
    return {k: normalize(raw.get(k, "")) for k in keys}


def is_blank(raw: dict, keys) -> bool:
    return not any(normalize(raw.get(k, "")) for k in keys)


# --------------------------------------------------------------- validation --
def _normalise_dates(cleaned: dict, fields) -> dict:
    """Store every date as DD.MM.YYYY, whatever shape it arrived in."""
    for key in fields:
        cleaned[key] = format_date(cleaned.get(key, ""))
    return cleaned


def validate_arc(raw: dict) -> dict:
    cleaned = _normalise_dates(_clean(raw, ARC_KEYS), ARC_DATE_FIELDS)
    if not cleaned["purchasing_document"]:
        raise ValidationError(
            ARC_LABELS["purchasing_document"],
            "is required - it is the contract every item and frame order hangs off",
        )
    return cleaned


def validate_fo(raw: dict) -> dict:
    cleaned = _normalise_dates(_clean(raw, FO_KEYS), FO_DATE_FIELDS)
    if not cleaned["frame_numbers"]:
        raise ValidationError(FO_LABELS["frame_numbers"], "is required")
    if not cleaned["contract_no"]:
        raise ValidationError(
            FO_LABELS["contract_no"],
            "is required - a frame order is always placed against a contract",
        )
    return cleaned


class _Table:
    """One CSV-backed list of dicts, keyed on one or more columns.

    Both tables are line-item level, so the key is composite: a document
    plus its item, a frame number plus its item. Re-importing the same
    export therefore updates the same rows instead of doubling them.
    """

    def __init__(self, path, keys, key_fields, validator, legacy=None, legacy_fn=None,
                 on_change=None):
        self.path = path
        self.keys = list(keys)
        self.key_fields = tuple(key_fields)
        self.validate = validator
        self.legacy = dict(legacy or {})
        # For a legacy column that has no single new home - two old columns
        # folded into one, say - a store may pass a function instead.
        self.legacy_fn = legacy_fn
        # Called whenever the rows change, so the store can drop the lookup
        # index it builds over them.
        self.on_change = on_change
        self.records = []
        self.load()

    # ------------------------------------------------------------- keys --
    def key_of(self, record):
        # Canonical, not raw: the same row re-imported from a differently
        # formatted export must land on itself rather than being duplicated.
        return tuple(document_key(record.get(k, "")) for k in self.key_fields)

    @staticmethod
    def row_id(key):
        return "␟".join(key)

    @staticmethod
    def key_from_id(row_id):
        return tuple(row_id.split("␟"))

    # ------------------------------------------------------------- disk --
    def load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.records = []
        if not os.path.exists(self.path):
            return
        frame = pd.read_csv(self.path, dtype=str, keep_default_na=False)
        for _, row in frame.iterrows():
            record = {k: normalize(row.get(k, "")) for k in self.keys}
            # A store written before the columns were renamed still loads:
            # an old column fills the new one when the new one is empty.
            for old, new in self.legacy.items():
                if not record.get(new) and normalize(row.get(old, "")):
                    record[new] = normalize(row.get(old, ""))
            if self.legacy_fn is not None:
                self.legacy_fn(record, row)
            if any(record.values()):
                self.records.append(record)
        self.changed()

    def changed(self):
        if self.on_change is not None:
            self.on_change()

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        pd.DataFrame(self.records, columns=self.keys).to_csv(self.path, index=False)
        self.changed()

    def find(self, key):
        """`key` is a tuple of the key columns, or a row id string."""
        if isinstance(key, str):
            key = self.key_from_id(key)
        needle = tuple(document_key(part) for part in key)
        if not any(needle):
            return None
        for record in self.records:
            if self.key_of(record) == needle:
                return record
        return None

    def group_by(self, field):
        """Rows grouped by one column, in first-seen order."""
        grouped = OrderedDict()
        for record in self.records:
            grouped.setdefault(normalize(record.get(field, "")), []).append(record)
        return grouped


class ArcStore:
    """Table 1 and Table 2, with every per-contract figure derived on read.

    One store owns both because they are only meaningful together: a frame
    order without its contract has nothing to be measured against, and a
    contract without its orders cannot say how much of itself is used.
    """

    def __init__(self, arc_path=ARC_FILE, fo_path=FO_FILE, change_log=None,
                 vendor_store=None):
        self.change_log = change_log
        # A vendor named on a contract or a frame order is created in the
        # vendor master the same way an equipment row creates one.
        self.vendor_store = vendor_store
        self._lock = threading.RLock()
        # Every read below - which frame orders belong to a contract, what a
        # contract has had released against it, what a frame order adds up to
        # - used to be a full scan of the other table. On a few thousand rows
        # that is a scan per row per column, and the grids crawled. They now
        # come off one index, built lazily and thrown away whenever either
        # table changes, so the answers can never be stale.
        self._index = None
        self.arcs = _Table(ARC_FILE if arc_path is None else arc_path,
                           ARC_KEYS, ARC_KEY_FIELDS, validate_arc, ARC_LEGACY_COLUMNS,
                           legacy_fn=self._legacy_vendor, on_change=self._invalidate)
        self.fos = _Table(FO_FILE if fo_path is None else fo_path,
                          FO_KEYS, FO_KEY_FIELDS, validate_fo, FO_LEGACY_COLUMNS,
                          on_change=self._invalidate)

    @staticmethod
    def _legacy_vendor(record, row):
        """An older store kept the vendor code and name in two columns; this
        table has the one combined column the export uses, so they are folded
        back together rather than dropped."""
        if record.get("vendor_supplying_plant"):
            return
        code = normalize(row.get("vendor_code", ""))
        name = normalize(row.get("vendor_name", ""))
        combined = " ".join(part for part in (code, name) if part)
        if combined:
            record["vendor_supplying_plant"] = combined

    # ----------------------------------------------------------- vendors --
    @staticmethod
    def vendor_of(record):
        """(code, name) for a row of either table."""
        if "vendor_supplying_plant" in record:
            return split_vendor(record.get("vendor_supplying_plant", ""))
        return (normalize(record.get("vendor", "")),
                normalize(record.get("vendor_name", "")))

    def _sync_vendor(self, record):
        if self.vendor_store is None:
            return None
        code, name = self.vendor_of(record)
        if not code or not code.isdigit():
            return None
        if self.vendor_store.get(code) is not None:
            return None
        try:
            self.vendor_store.upsert({"vendor_code": code, "vendor_name": name})
        except ValidationError:
            return None
        return (code, name)

    # ------------------------------------------------------------- index --
    def _invalidate(self):
        self._index = None

    def _build_index(self):
        """One pass over both tables; every read below is a dict lookup after."""
        documents = OrderedDict()
        for record in self.arcs.records:
            key = document_key(record.get("purchasing_document", ""))
            entry = documents.get(key)
            if entry is None:
                entry = documents[key] = {
                    "document": normalize(record.get("purchasing_document", "")),
                    "header": {field: "" for field in ARC_HEADER_KEYS},
                    "items": [],
                }
            entry["items"].append(record)
            header = entry["header"]
            # The header is whatever the first row carrying each field says:
            # an export can leave a repeated cell blank on continuation rows,
            # and the contract still has one value for it.
            for field in ARC_HEADER_KEYS:
                if not header[field]:
                    header[field] = normalize(record.get(field, ""))

        fos_by_contract = {}
        items_by_frame = OrderedDict()
        frames_by_contract = OrderedDict()
        released_by_contract = {}
        frame_totals = {}
        for record in self.fos.records:
            contract = document_key(record.get("contract_no", ""))
            fos_by_contract.setdefault(contract, []).append(record)

            written = normalize(record.get("frame_numbers", ""))
            frame = document_key(written)
            items_by_frame.setdefault(frame, []).append(record)
            if frame:
                seen = frames_by_contract.setdefault(contract, OrderedDict())
                seen.setdefault(frame, written)

            released = parse_amount(record.get("released_value", ""))
            released_by_contract[contract] = released_by_contract.get(contract, 0.0) + released
            totals = frame_totals.setdefault(
                frame, {"released_value": 0.0, "actual_value": 0.0, "opening_value": 0.0}
            )
            for field in totals:
                totals[field] += parse_amount(record.get(field, ""))

        return {
            "documents": documents,
            "fos_by_contract": fos_by_contract,
            "items_by_frame": items_by_frame,
            "frames_by_contract": frames_by_contract,
            "released_by_contract": released_by_contract,
            "frame_totals": frame_totals,
        }

    def _idx(self):
        if self._index is None:
            self._index = self._build_index()
        return self._index

    # ------------------------------------------------------------- reads --
    def all_arcs(self):
        return list(self.arcs.records)

    def all_fos(self):
        return list(self.fos.records)

    def items_for_document(self, document):
        entry = self._idx()["documents"].get(document_key(document))
        return list(entry["items"]) if entry else []

    def fos_for_document(self, document):
        """Every Table 2 row whose Contract No. names this document.

        The join between the two files, so it compares canonical numbers -
        see document_key. Matching the raw text here is what would report a
        contract with frame orders as having none.
        """
        return list(self._idx()["fos_by_contract"].get(document_key(document), []))

    def items_for_frame(self, frame):
        return list(self._idx()["items_by_frame"].get(document_key(frame), []))

    def frames_for_document(self, document):
        """The distinct frame orders raised against a contract.

        Distinct by canonical frame number, but each is reported as it was
        written, so the screen shows what is in the file.
        """
        seen = self._idx()["frames_by_contract"].get(document_key(document))
        return list(seen.values()) if seen else []

    # --------------------------------------------------------- roll-ups --
    def documents(self):
        """One entry per purchasing document, keyed canonically, header read
        once. Read-only: it is the store's own index, not a copy."""
        return self._idx()["documents"]

    def header_for(self, document):
        entry = self.documents().get(document_key(document))
        return entry["header"] if entry else {}

    def target_value(self, document) -> float:
        """The contract's planned value, taken ONCE from the header.

        Target Val. (Header) repeats on every item of the document, so this
        deliberately reads a single occurrence. Summing the column is the
        one mistake that would silently multiply every contract's worth.
        """
        return parse_amount(self.header_for(document).get("target_value", ""))

    def frame_released(self, frame) -> float:
        """What one frame order has released: its items DO add up."""
        return self.frame_value(frame, "released_value")

    def frame_value(self, frame, key) -> float:
        totals = self._idx()["frame_totals"].get(document_key(frame))
        return totals[key] if totals else 0.0

    def released_against(self, document) -> float:
        """Released against a contract: every item of every frame order on it."""
        return self._idx()["released_by_contract"].get(document_key(document), 0.0)

    def value_gap(self, document) -> float:
        """Target Val. (Header) - what has been released against it.

        Positive means contract value still to be ordered; negative means
        the frame orders have over-run the contract, which is the alarming
        case and is why the sign is kept rather than shown as a magnitude.
        """
        return self.target_value(document) - self.released_against(document)

    # ------------------------------------------------------- grid rows --
    def arc_row(self, record: dict) -> dict:
        """A Table 1 row plus its document-level derived columns.

        Those repeat down the items of a document exactly the way Target
        Val. (Header) does in the source report - the same fact about the
        same contract, shown on each of its rows.
        """
        document = normalize(record.get("purchasing_document", ""))
        enriched = dict(record)
        for key in ARC_DATE_FIELDS:
            enriched[key] = format_date(record.get(key, ""))
        enriched["target_value"] = display_amount(record.get("target_value", ""))
        enriched["frame_orders"] = str(len(self.frames_for_document(document)))
        enriched["ordered_value"] = format_amount(self.released_against(document))
        enriched["value_difference"] = format_amount(self.value_gap(document))
        return enriched

    def fo_row(self, record: dict) -> dict:
        frame = normalize(record.get("frame_numbers", ""))
        enriched = dict(record)
        for key in FO_DATE_FIELDS:
            enriched[key] = format_date(record.get(key, ""))
        for key in ["contract_value"] + FO_ITEM_VALUE_KEYS:
            enriched[key] = display_amount(record.get(key, ""))
        enriched["fo_items"] = str(len(self.items_for_frame(frame)))
        enriched["fo_released_total"] = format_amount(self.frame_released(frame))
        return enriched

    def summary(self) -> dict:
        index = self._idx()
        documents = index["documents"]
        target = sum(parse_amount(e["header"].get("target_value", ""))
                     for e in documents.values())
        released = sum(index["released_by_contract"].values())
        known = set(documents)          # already canonical keys
        orphan_frames = {
            document_key(r.get("frame_numbers", ""))
            for contract, rows in index["fos_by_contract"].items()
            if contract not in known
            for r in rows
        }
        frames = set(index["items_by_frame"])
        return {
            "arcs": len(documents),
            "arc_items": len(self.arcs.records),
            "fos": len({f for f in frames if f}),
            "fo_items": len(self.fos.records),
            "target_value": target,
            "value": released,
            "gap": target - released,
            "orphan_fos": len({f for f in orphan_frames if f}),
        }

    def structure(self) -> list:
        """The contract -> (items, frame orders -> items) tree, in display order.

        A frame order whose Contract No. matches no document is grouped
        under a synthetic "(no contract on file)" node rather than being
        dropped - an order against a mistyped contract has to stay visible.
        """
        tree = []
        for entry in self.documents().values():
            document = entry["document"]
            tree.append({
                "document": document,
                "header": entry["header"],
                "items": entry["items"],
                "frames": self._frame_nodes(self.fos_for_document(document)),
                "target": parse_amount(entry["header"].get("target_value", "")),
                "released": self.released_against(document),
            })

        known = set(self.documents())   # already canonical keys
        orphans = [r for r in self.fos.records
                   if document_key(r.get("contract_no", "")) not in known]
        if orphans:
            tree.append({
                "document": "(no contract on file)",
                "header": {"short_text": "Frame orders whose Contract No. matches "
                                         "no purchasing document"},
                "items": [],
                "frames": self._frame_nodes(orphans),
                "target": 0.0,
                "released": sum(parse_amount(r.get("released_value", "")) for r in orphans),
                "orphan": True,
            })
        return tree

    @staticmethod
    def _frame_nodes(rows):
        grouped = OrderedDict()
        for row in rows:
            grouped.setdefault(normalize(row.get("frame_numbers", "")), []).append(row)
        return [
            {
                "frame": frame,
                "items": items,
                "released": sum(parse_amount(r.get("released_value", "")) for r in items),
                "header": items[0],
            }
            for frame, items in grouped.items()
        ]

    # ------------------------------------------------------------ writes --
    def _log(self, document, reference, action, details):
        if self.change_log is not None and details:
            self.change_log.record(document, reference, action, details)

    def _upsert(self, table, raw, level, document_of, reference_of, labels):
        """Shared insert-or-merge for both tables.

        Same cell-level merge rule as the other masters: a blank incoming
        cell never overwrites what is already stored.
        """
        cleaned = table.validate(raw)
        with self._lock:
            existing = table.find(table.key_of(cleaned))
            if existing is not None:
                changes = [
                    f"{labels[k]}: '{existing.get(k, '')}' -> '{cleaned[k]}'"
                    for k in table.keys
                    if cleaned[k] and cleaned[k] != existing.get(k, "")
                ]
                for key in table.keys:
                    if cleaned[key]:
                        existing[key] = cleaned[key]
                target, result = existing, "updated"
                details = "; ".join(changes)
            else:
                table.records.append(cleaned)
                target, result = cleaned, "added"
                details = f"New {level} created"
            table.save()
            created = self._sync_vendor(target)

        self._log(
            document_of(target), reference_of(target),
            "Added" if result == "added" else "Updated", details,
        )
        if created:
            self._log(
                document_of(target), created[0], "Vendor Added",
                f"Vendor {created[0]} auto-created in the vendor master from a {level}",
            )
        return result

    def upsert_arc(self, raw):
        return self._upsert(
            self.arcs, raw, "contract item",
            lambda r: r.get("purchasing_document", ""),
            lambda r: f"Item {r.get('item', '')}".strip(),
            ARC_LABELS,
        )

    def upsert_fo(self, raw):
        return self._upsert(
            self.fos, raw, "frame order item",
            lambda r: r.get("contract_no", ""),
            lambda r: f"{r.get('frame_numbers', '')} item {r.get('item', '')}".strip(),
            FO_LABELS,
        )

    def _bulk(self, table, rows, upsert, progress=None):
        added = updated = 0
        errors = []
        total = len(rows)
        for index, raw in enumerate(rows, start=1):
            if not is_blank(raw, table.keys):
                try:
                    if upsert(raw) == "added":
                        added += 1
                    else:
                        updated += 1
                except ValidationError as exc:
                    errors.append((index, str(exc)))
            if progress is not None and (index % 100 == 0 or index == total):
                progress(index, total)
        return {"added": added, "updated": updated, "errors": errors}

    def bulk_upsert_arcs(self, rows, progress=None):
        return self._bulk(self.arcs, rows, self.upsert_arc, progress)

    def bulk_upsert_fos(self, rows, progress=None):
        return self._bulk(self.fos, rows, self.upsert_fo, progress)

    # ------------------------------------------------------------ update --
    def update_arc_field(self, row_id, key, value):
        return self._update(self.arcs, row_id, key, value, ARC_LABELS,
                            lambda r: r.get("purchasing_document", ""),
                            lambda r: f"Item {r.get('item', '')}".strip())

    def update_fo_field(self, row_id, key, value):
        return self._update(self.fos, row_id, key, value, FO_LABELS,
                            lambda r: r.get("contract_no", ""),
                            lambda r: f"{r.get('frame_numbers', '')} "
                                      f"item {r.get('item', '')}".strip())

    def _update(self, table, row_id, key, value, labels, document_of, reference_of):
        if key in table.key_fields:
            raise ValidationError(
                labels[key], "identifies the row and cannot be changed here"
            )
        with self._lock:
            record = table.find(row_id)
            if record is None:
                raise ValidationError("This row", "no longer exists - refresh and try again")
            before = record.get(key, "")
            candidate = dict(record)
            candidate[key] = normalize(value)
            cleaned = table.validate(candidate)
            record.update(cleaned)
            table.save()
        self._log(
            document_of(record), reference_of(record), "Updated",
            f"{labels.get(key, key)}: '{before}' -> '{record.get(key, '')}'",
        )
        return record

    # ------------------------------------------------------------ delete --
    def delete_arc(self, row_id):
        """Remove one contract item. The last item of a document takes the
        document's frame orders with it - an order against a contract that
        no longer exists has nothing to be measured against."""
        with self._lock:
            record = self.arcs.find(row_id)
            if record is None:
                return False
            document = normalize(record.get("purchasing_document", ""))
            self.arcs.records.remove(record)
            removed_frames = 0
            if not self.items_for_document(document):
                for row in self.fos_for_document(document):
                    self.fos.records.remove(row)
                    removed_frames += 1
                self.fos.save()
            self.arcs.save()
        detail = f"Item {record.get('item', '')} deleted"
        if removed_frames:
            detail += (f"; last item of the contract, so {removed_frames} "
                       "frame order row(s) went with it")
        self._log(document, f"Item {record.get('item', '')}".strip(), "Deleted", detail)
        return True

    def delete_document(self, document):
        """Remove a whole purchasing document: its items and its orders."""
        with self._lock:
            items = self.items_for_document(document)
            frames = self.fos_for_document(document)
            if not items and not frames:
                return False
            for row in items:
                self.arcs.records.remove(row)
            for row in frames:
                self.fos.records.remove(row)
            self.arcs.save()
            self.fos.save()
        self._log(
            document, "", "Deleted",
            f"Contract deleted with {len(items)} item(s) and {len(frames)} "
            "frame order row(s)",
        )
        return True

    def delete_fo(self, row_id):
        with self._lock:
            record = self.fos.find(row_id)
            if record is None:
                return False
            self.fos.records.remove(record)
            self.fos.save()
        self._log(
            record.get("contract_no", ""),
            f"{record.get('frame_numbers', '')} item {record.get('item', '')}".strip(),
            "Deleted", "Frame order item deleted",
        )
        return True
