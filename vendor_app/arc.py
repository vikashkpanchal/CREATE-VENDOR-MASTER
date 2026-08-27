"""ARC & FO master: rate contracts, the orders beneath them, and their lines.

The hierarchy is the point of this module:

    ARC  (arc_no)          the master agreement - the key every amendment is
     |                     filed against
     +-- FO  (fo_no)       a sub-part of the ARC; one ARC carries many FOs
          +-- line item    the reference rows an FO's value is made of

Value only ever flows UP that tree, never down and never sideways:

    line value  = the figure entered, or quantity x rate when it is blank
    FO total    = the sum of its line items, or the FO's own entered value
                  when it has no lines yet
    ARC value   = the sum of the FO totals beneath it

So "ARC value" is always the final aggregated value of that ARC's FOs. It is
derived on read and never stored, which means it cannot drift out of step
with the orders it is supposed to summarise.
"""

import os
import re
import threading
from datetime import date, datetime

import pandas as pd

from vendor_app.config import (
    ARC_FILE,
    ARC_KEYS,
    ARC_LABELS,
    ARC_LINE_ITEM_FILE,
    ARC_LINE_KEYS,
    ARC_LINE_LABELS,
    ARC_STATUS_DEFAULT,
    DATA_DIR,
    FO_FILE,
    FO_KEYS,
    FO_LABELS,
    FO_STATUS_DEFAULT,
)
from vendor_app.validators import ValidationError, normalize

_NUMBER_RE = re.compile(r"[^0-9.\-]")


def parse_amount(value) -> float:
    """Read a money/quantity cell leniently.

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


# Dates arrive from ME3L/SAP exports and from hand-typed cells alike, so
# every shape either of those produces has to read. SAP's own dotted format
# leads because that is what an untouched download contains.
DATE_FORMATS = (
    "%d.%m.%Y", "%d.%m.%y",
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
    "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
)


def parse_date(value):
    """Read a validity date leniently. Returns a date, or None if unreadable.

    An unreadable date must never be guessed at: it is reported as "no date"
    and counted separately, because silently treating it as expired - or as
    active - would put a wrong contract in front of management.
    """
    text = normalize(value)
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def days_until(value, today=None) -> int:
    """Days from `today` to `value`; negative once it has passed.

    Returns None when the date cannot be read, so callers can keep those
    rows out of the expiry buckets instead of bucketing them wrongly.
    """
    end = parse_date(value)
    if end is None:
        return None
    return (end - (today or date.today())).days


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


def _clean(raw: dict, keys) -> dict:
    return {k: normalize(raw.get(k, "")) for k in keys}


def is_blank(raw: dict, keys) -> bool:
    return not any(normalize(raw.get(k, "")) for k in keys)


# --------------------------------------------------------------- validation --
def validate_arc(raw: dict) -> dict:
    cleaned = _clean(raw, ARC_KEYS)
    if not cleaned["arc_no"]:
        raise ValidationError(ARC_LABELS["arc_no"], "is required - it is the master key")
    if not cleaned["status"]:
        cleaned["status"] = ARC_STATUS_DEFAULT
    return cleaned


def validate_fo(raw: dict) -> dict:
    cleaned = _clean(raw, FO_KEYS)
    if not cleaned["fo_no"]:
        raise ValidationError(FO_LABELS["fo_no"], "is required")
    if not cleaned["arc_no"]:
        raise ValidationError(
            FO_LABELS["arc_no"], "is required - every FO belongs to exactly one ARC"
        )
    if not cleaned["status"]:
        cleaned["status"] = FO_STATUS_DEFAULT
    return cleaned


def validate_line(raw: dict) -> dict:
    cleaned = _clean(raw, ARC_LINE_KEYS)
    if not cleaned["fo_no"]:
        raise ValidationError(
            ARC_LINE_LABELS["fo_no"], "is required - a line item references one FO"
        )
    if not cleaned["line_no"] and not cleaned["item_code"]:
        raise ValidationError(
            ARC_LINE_LABELS["line_no"], "or Item Code is required to identify the line"
        )
    return cleaned


def line_value(record: dict) -> float:
    """A line's value: the figure entered, else quantity x rate."""
    entered = normalize(record.get("line_value", ""))
    if entered:
        return parse_amount(entered)
    return parse_amount(record.get("quantity", "")) * parse_amount(record.get("rate", ""))


class _Table:
    """One CSV-backed list of dicts with a single-column key.

    Kept deliberately small: three of these, plus the roll-up rules in
    ArcStore, is the whole module.
    """

    def __init__(self, path, keys, key_field, validator):
        self.path = path
        self.keys = list(keys)
        self.key_field = key_field
        self.validate = validator
        self.records = []
        self.load()

    def load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.records = []
        if os.path.exists(self.path):
            frame = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            for _, row in frame.iterrows():
                record = {k: normalize(row.get(k, "")) for k in self.keys}
                if any(record.values()):
                    self.records.append(record)

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        pd.DataFrame(self.records, columns=self.keys).to_csv(self.path, index=False)

    def find(self, key_value):
        needle = normalize(key_value).lower()
        if not needle:
            return None
        for record in self.records:
            if record.get(self.key_field, "").lower() == needle:
                return record
        return None


class ArcStore:
    """The ARC master, its FOs and their line items, with value roll-up.

    A single store owns all three levels because they are only ever
    meaningful together - an FO without its ARC, or a value without the
    lines behind it, is not something the app should be able to represent.
    """

    def __init__(self, arc_path=ARC_FILE, fo_path=FO_FILE, line_path=ARC_LINE_ITEM_FILE,
                 change_log=None, vendor_store=None):
        self.change_log = change_log
        # A vendor named on an ARC or FO is created in the vendor master the
        # same way an equipment row creates one, so the masters stay in step.
        self.vendor_store = vendor_store
        self._lock = threading.RLock()
        self.arcs = _Table(arc_path, ARC_KEYS, "arc_no", validate_arc)
        self.fos = _Table(fo_path, FO_KEYS, "fo_no", validate_fo)
        self.lines = _Table(line_path, ARC_LINE_KEYS, "line_no", validate_line)

    # ----------------------------------------------------------- vendors --
    def _sync_vendor(self, record):
        if self.vendor_store is None:
            return None
        code = normalize(record.get("vendor_code", ""))
        if not code or not code.isdigit():
            return None
        if self.vendor_store.get(code) is not None:
            return None
        name = normalize(record.get("vendor_name", ""))
        try:
            self.vendor_store.upsert({"vendor_code": code, "vendor_name": name})
        except ValidationError:
            return None
        return (code, name)

    # ------------------------------------------------------------- reads --
    def all_arcs(self):
        return list(self.arcs.records)

    def all_fos(self):
        return list(self.fos.records)

    def all_lines(self):
        return list(self.lines.records)

    def fos_for_arc(self, arc_no):
        needle = normalize(arc_no).lower()
        return [f for f in self.fos.records if f.get("arc_no", "").lower() == needle]

    def lines_for_fo(self, fo_no):
        needle = normalize(fo_no).lower()
        return [l for l in self.lines.records if l.get("fo_no", "").lower() == needle]

    # --------------------------------------------------------- roll-ups --
    def fo_total(self, fo_no) -> float:
        """An FO's effective value: its line items, or its own figure when
        it has none. Lines are the reference, so once they exist they win."""
        lines = self.lines_for_fo(fo_no)
        if lines:
            return sum(line_value(l) for l in lines)
        record = self.fos.find(fo_no)
        return parse_amount(record.get("fo_value", "")) if record else 0.0

    def fo_value_for_arc(self, arc_no) -> float:
        """What has actually been ordered against an ARC: the sum of its FOs."""
        return sum(self.fo_total(f.get("fo_no", "")) for f in self.fos_for_arc(arc_no))

    def arc_target_value(self, arc_no) -> float:
        """The ARC's own released value, as it came out of ME3L."""
        record = self.arcs.find(arc_no)
        return parse_amount(record.get("arc_value", "")) if record else 0.0

    def value_gap(self, arc_no) -> float:
        """ARC Value - Sum of FO Values: the balance still open on the contract.

        Positive means budget released but not yet ordered against; negative
        means the FOs have over-run the contract, which is the alarming case.
        """
        return self.arc_target_value(arc_no) - self.fo_value_for_arc(arc_no)

    def arc_row(self, record: dict) -> dict:
        """An ARC record plus its derived columns, ready for the grid."""
        arc_no = record.get("arc_no", "")
        enriched = dict(record)
        enriched["arc_value"] = display_amount(record.get("arc_value", ""))
        enriched["fo_count"] = str(len(self.fos_for_arc(arc_no)))
        enriched["fo_value_total"] = format_amount(self.fo_value_for_arc(arc_no))
        enriched["value_difference"] = format_amount(self.value_gap(arc_no))
        return enriched

    def fo_row(self, record: dict) -> dict:
        fo_no = record.get("fo_no", "")
        enriched = dict(record)
        for key in ("fo_value", "released_value", "open_value"):
            enriched[key] = display_amount(record.get(key, ""))
        enriched["line_count"] = str(len(self.lines_for_fo(fo_no)))
        enriched["fo_total"] = format_amount(self.fo_total(fo_no))
        return enriched

    def line_row(self, record: dict) -> dict:
        enriched = dict(record)
        if not normalize(enriched.get("line_value", "")):
            # Show what the line is actually worth, even when only the
            # quantity and rate were entered.
            enriched["line_value"] = format_amount(line_value(record))
        return enriched

    def summary(self) -> dict:
        arcs = self.all_arcs()
        fo_value = sum(self.fo_value_for_arc(a.get("arc_no", "")) for a in arcs)
        target = sum(parse_amount(a.get("arc_value", "")) for a in arcs)
        return {
            "arcs": len(arcs),
            "fos": len(self.fos.records),
            "lines": len(self.lines.records),
            "value": fo_value,
            "target_value": target,
            "gap": target - fo_value,
            "orphan_fos": len([
                f for f in self.fos.records
                if self.arcs.find(f.get("arc_no", "")) is None
            ]),
        }

    def structure(self) -> list:
        """The full ARC -> FO -> line tree, in display order.

        FOs whose ARC No matches no ARC record are grouped under a synthetic
        "(no ARC on file)" node rather than being dropped - an order with a
        mistyped ARC has to stay visible or it silently disappears.
        """
        tree = []
        for arc in self.arcs.records:
            arc_no = arc.get("arc_no", "")
            fos = []
            for fo in self.fos_for_arc(arc_no):
                fo_no = fo.get("fo_no", "")
                fos.append({
                    "record": fo,
                    "total": self.fo_total(fo_no),
                    "lines": [
                        {"record": l, "value": line_value(l)}
                        for l in self.lines_for_fo(fo_no)
                    ],
                })
            tree.append({
                "record": arc,
                "fos": fos,
                "total": self.fo_value_for_arc(arc_no),
                "target": parse_amount(arc.get("arc_value", "")),
            })

        known = {a.get("arc_no", "").lower() for a in self.arcs.records}
        orphans = [f for f in self.fos.records if f.get("arc_no", "").lower() not in known]
        if orphans:
            fos = []
            for fo in orphans:
                fo_no = fo.get("fo_no", "")
                fos.append({
                    "record": fo,
                    "total": self.fo_total(fo_no),
                    "lines": [
                        {"record": l, "value": line_value(l)}
                        for l in self.lines_for_fo(fo_no)
                    ],
                })
            tree.append({
                "record": {"arc_no": "(no ARC on file)", "arc_description":
                           "FOs whose ARC No does not match any ARC record"},
                "fos": fos,
                "total": sum(f["total"] for f in fos),
                "target": 0.0,
                "orphan": True,
            })
        return tree

    # ------------------------------------------------------------ writes --
    def _log(self, arc_no, reference, action, details):
        if self.change_log is not None and details:
            self.change_log.record(arc_no, reference, action, details)

    def _upsert(self, table, raw, level, arc_of, name_of, labels):
        """Shared insert-or-merge for all three levels.

        Same cell-level merge rule as the other masters: a blank incoming
        cell never overwrites what is already stored.
        """
        cleaned = table.validate(raw)
        with self._lock:
            existing = table.find(cleaned[table.key_field])
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
            arc_of(target), name_of(target),
            "Added" if result == "added" else "Updated", details,
        )
        if created:
            self._log(
                arc_of(target), created[0], "Vendor Added",
                f"Vendor {created[0]} auto-created in the vendor master from an {level}",
            )
        return result

    def upsert_arc(self, raw):
        return self._upsert(
            self.arcs, raw, "ARC",
            lambda r: r.get("arc_no", ""), lambda r: r.get("arc_description", ""), ARC_LABELS,
        )

    def upsert_fo(self, raw):
        return self._upsert(
            self.fos, raw, "FO",
            lambda r: r.get("arc_no", ""), lambda r: f"FO {r.get('fo_no', '')}", FO_LABELS,
        )

    def upsert_line(self, raw):
        return self._upsert(
            self.lines, raw, "line item",
            lambda r: r.get("arc_no", ""),
            lambda r: f"FO {r.get('fo_no', '')} line {r.get('line_no', '')}",
            ARC_LINE_LABELS,
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

    def bulk_upsert_lines(self, rows, progress=None):
        return self._bulk(self.lines, rows, self.upsert_line, progress)

    # ------------------------------------------------------------ update --
    def update_arc_field(self, arc_no, key, value):
        return self._update(self.arcs, arc_no, key, value, "arc_no", ARC_LABELS,
                            lambda r: r.get("arc_no", ""))

    def update_fo_field(self, fo_no, key, value):
        return self._update(self.fos, fo_no, key, value, "fo_no", FO_LABELS,
                            lambda r: r.get("arc_no", ""))

    def _update(self, table, key_value, key, value, pk, labels, arc_of):
        if key == pk:
            raise ValidationError(labels[pk], "is the key and cannot be changed here")
        with self._lock:
            record = table.find(key_value)
            if record is None:
                raise ValidationError(labels[pk], "no longer exists - refresh and try again")
            before = record.get(key, "")
            candidate = dict(record)
            candidate[key] = normalize(value)
            cleaned = table.validate(candidate)
            record.update(cleaned)
            table.save()
        self._log(
            arc_of(record), record.get(pk, ""), "Updated",
            f"{labels.get(key, key)}: '{before}' -> '{record.get(key, '')}'",
        )
        return record

    def update_line_field(self, record, key, value):
        """Line items have no single stable key, so the row object is passed."""
        if record is None:
            raise ValidationError("Line item", "no longer exists - refresh and try again")
        with self._lock:
            before = record.get(key, "")
            candidate = dict(record)
            candidate[key] = normalize(value)
            cleaned = validate_line(candidate)
            record.update(cleaned)
            self.lines.save()
        self._log(
            record.get("arc_no", ""),
            f"FO {record.get('fo_no', '')} line {record.get('line_no', '')}",
            "Updated", f"{ARC_LINE_LABELS.get(key, key)}: '{before}' -> '{record.get(key, '')}'",
        )
        return record

    # ------------------------------------------------------------ delete --
    def delete_arc(self, arc_no, cascade=True):
        """Remove an ARC. Its FOs and their lines go with it by default -
        an order under no contract has nothing to be an amendment of."""
        with self._lock:
            record = self.arcs.find(arc_no)
            if record is None:
                return False
            self.arcs.records.remove(record)
            removed_fos = removed_lines = 0
            if cascade:
                for fo in self.fos_for_arc(arc_no):
                    removed_lines += self._drop_lines(fo.get("fo_no", ""))
                    self.fos.records.remove(fo)
                    removed_fos += 1
                self.fos.save()
                self.lines.save()
            self.arcs.save()
        self._log(
            arc_no, record.get("arc_description", ""), "Deleted",
            f"ARC deleted along with {removed_fos} FO(s) and {removed_lines} line item(s)",
        )
        return True

    def _drop_lines(self, fo_no):
        lines = self.lines_for_fo(fo_no)
        for line in lines:
            self.lines.records.remove(line)
        return len(lines)

    def delete_fo(self, fo_no):
        with self._lock:
            record = self.fos.find(fo_no)
            if record is None:
                return False
            removed = self._drop_lines(fo_no)
            self.fos.records.remove(record)
            self.fos.save()
            self.lines.save()
        self._log(
            record.get("arc_no", ""), f"FO {fo_no}", "Deleted",
            f"FO deleted along with {removed} line item(s)",
        )
        return True

    def delete_line(self, record):
        if record is None:
            return False
        with self._lock:
            if record not in self.lines.records:
                return False
            self.lines.records.remove(record)
            self.lines.save()
        self._log(
            record.get("arc_no", ""),
            f"FO {record.get('fo_no', '')} line {record.get('line_no', '')}",
            "Deleted", "Line item deleted",
        )
        return True
