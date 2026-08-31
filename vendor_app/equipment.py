"""Equipment master: rental/hired equipment supplied by vendors.

Not every vendor hires equipment out, so this is a separate dataset keyed
by its own identifiers rather than an extension of the vendor record. Any
one of RH/RO Number, Technical ID or Reg No uniquely identifies a machine,
so a search can start from whichever of the three the user has to hand.
"""

import os
import threading

import pandas as pd

from vendor_app.config import (
    LEASE_TYPE_VALUES,
    DATA_DIR,
    DEMOB_FIELD,
    EQUIPMENT_FILE,
    EQUIPMENT_KEYS,
    EQUIPMENT_LABELS,
    EQUIPMENT_LOOKUP_KEYS,
    EQUIPMENT_NUMERIC_FIELDS,
)
from vendor_app.validators import ValidationError, normalize, validate_choice


def is_demobbed(record: dict) -> bool:
    """A machine with a De-mob Date has left site: its record is closed."""
    return bool(normalize((record or {}).get(DEMOB_FIELD, "")))


def equipment_id(record: dict) -> str:
    """The identifier a machine is known by in the change log - whichever of
    the three unique identifiers it actually carries."""
    for key in EQUIPMENT_LOOKUP_KEYS:
        if record.get(key):
            return record[key]
    return ""


def validate_equipment(raw: dict) -> dict:
    """Normalize a raw equipment row and enforce the few hard rules:
    at least one lookup identifier, and Technical ID numeric when present."""
    cleaned = {k: normalize(raw.get(k, "")) for k in EQUIPMENT_KEYS}

    for key in EQUIPMENT_NUMERIC_FIELDS:
        if cleaned[key] and not cleaned[key].isdigit():
            raise ValidationError(EQUIPMENT_LABELS[key], "must be a number")

    # Dry or wet hire, and nothing else - the same rule Vendor Type follows.
    cleaned["lease_type"] = validate_choice(
        cleaned["lease_type"], EQUIPMENT_LABELS["lease_type"], LEASE_TYPE_VALUES
    )

    if not any(cleaned[k] for k in EQUIPMENT_LOOKUP_KEYS):
        labels = " / ".join(EQUIPMENT_LABELS[k] for k in EQUIPMENT_LOOKUP_KEYS)
        raise ValidationError(labels, "at least one identifier is required")

    return cleaned


def is_blank_equipment(raw: dict) -> bool:
    return not any(normalize(raw.get(k, "")) for k in EQUIPMENT_KEYS)


class EquipmentStore:
    """CRUD + multi-key lookup over the equipment master dataset."""

    def __init__(self, path: str = EQUIPMENT_FILE, change_log=None, vendor_store=None):
        self.path = path
        self.change_log = change_log
        # When set, any vendor referenced by an equipment row that is not yet
        # in the vendor master is created there automatically (code + name).
        self.vendor_store = vendor_store
        self._lock = threading.Lock()
        self._records = []           # list of cleaned dicts, display order
        self._index = {}             # (lookup_key, value.lower()) -> record
        self.load()

    # --------------------------------------------------- vendor sync --
    def _sync_vendor(self, record: dict):
        """Ensure the row's vendor exists in the vendor master.

        Returns a (code, name) tuple when a vendor was created, else None.
        Only the code and name are seeded - contact details stay for the
        user to fill in, and an existing vendor is never overwritten here.
        """
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

    # ---------------------------------------------------------------- IO --
    def load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._records = []
        if os.path.exists(self.path):
            df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            for _, row in df.iterrows():
                record = {k: normalize(row.get(k, "")) for k in EQUIPMENT_KEYS}
                if any(record.values()):
                    self._records.append(record)
        self._reindex()

    def _reindex(self):
        """Rebuild the identifier -> record index.

        Only RUNNING records are indexed. A de-mobbed record is closed: it
        must not absorb an update, and if the same machine comes back on
        site its row has to be created fresh rather than reopening the old
        one. Closed records stay searchable through _find_demobbed().
        """
        self._index = {}
        for record in self._records:
            if is_demobbed(record):
                continue
            for key in EQUIPMENT_LOOKUP_KEYS:
                value = record.get(key, "")
                if value:
                    self._index[(key, value.lower())] = record

    def _find_demobbed(self, identifier: str):
        """The most recent closed record carrying this identifier."""
        value = normalize(identifier).lower()
        if not value:
            return None
        for record in reversed(self._records):
            if not is_demobbed(record):
                continue
            if any(str(record.get(k, "")).lower() == value for k in EQUIPMENT_LOOKUP_KEYS):
                return record
        return None

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        df = pd.DataFrame(self._records, columns=EQUIPMENT_KEYS)
        df.to_csv(self.path, index=False)

    # ------------------------------------------------------------ Writes --
    def _find_existing(self, cleaned: dict):
        return self._index_lookup(cleaned)

    def upsert(self, raw: dict) -> str:
        """Insert or merge one equipment row, matched on any shared
        identifier. Same cell-level merge rule as the vendor master: only
        non-blank incoming fields overwrite what is already stored."""
        cleaned = validate_equipment(raw)
        with self._lock:
            existing = self._find_existing(cleaned)
            if existing is not None:
                changes = [
                    f"{EQUIPMENT_LABELS[key]}: '{existing.get(key, '')}' -> '{cleaned[key]}'"
                    for key in EQUIPMENT_KEYS
                    if cleaned[key] and cleaned[key] != existing.get(key, "")
                ]
                for key in EQUIPMENT_KEYS:
                    if cleaned[key]:
                        existing[key] = cleaned[key]
                result, target = "updated", existing
                details = "; ".join(changes) if changes else ""
            else:
                self._records.append(cleaned)
                result, target = "added", cleaned
                details = "New equipment record created"
            self._reindex()
            self.save()
            created_vendor = self._sync_vendor(target)

        if self.change_log is not None and details:
            self.change_log.record(
                equipment_id(target), target.get("equipment_description", ""),
                "Added" if result == "added" else "Updated", details,
            )
        if created_vendor:
            self._log_vendor_autocreate(*created_vendor)
        return result

    def upsert_demobbed(self, raw: dict) -> str:
        """Insert or merge a CLOSED record - the import side of the de-mob list.

        Matched against closed records only. Re-importing a list this app
        exported therefore updates those same rows instead of creating a
        second copy of every machine, and it can never reopen or overwrite a
        machine that is currently on site: closing one of those is the
        De-mob action's job, which writes its own change-log entry.
        """
        cleaned = validate_equipment(raw)
        if not is_demobbed(cleaned):
            raise ValidationError(
                EQUIPMENT_LABELS[DEMOB_FIELD],
                "is required on a de-mob import - a row without it is not a "
                "closed record",
            )
        identifier = equipment_id(cleaned)
        with self._lock:
            if self._index_lookup(cleaned) is not None:
                raise ValidationError(
                    identifier,
                    "is still running - de-mob it from the De-mob screen rather "
                    "than importing it as closed",
                )
            existing = self._find_demobbed(identifier)
            if existing is not None:
                changes = [
                    f"{EQUIPMENT_LABELS[key]}: '{existing.get(key, '')}' -> '{cleaned[key]}'"
                    for key in EQUIPMENT_KEYS
                    if cleaned[key] and cleaned[key] != existing.get(key, "")
                ]
                for key in EQUIPMENT_KEYS:
                    if cleaned[key]:
                        existing[key] = cleaned[key]
                result, target = "updated", existing
                details = "; ".join(changes)
            else:
                self._records.append(cleaned)
                result, target = "added", cleaned
                details = "De-mobbed record imported"
            self._reindex()
            self.save()

        if self.change_log is not None and details:
            self.change_log.record(
                equipment_id(target), target.get("equipment_description", ""),
                "Imported (de-mob)", details,
            )
        return result

    def _index_lookup(self, cleaned):
        """The RUNNING record sharing an identifier with `cleaned`, if any."""
        for key in EQUIPMENT_LOOKUP_KEYS:
            value = cleaned.get(key, "")
            if value:
                found = self._index.get((key, value.lower()))
                if found is not None:
                    return found
        return None

    def bulk_upsert_demobbed(self, rows: list, progress=None) -> dict:
        added = updated = 0
        errors = []
        total = len(rows)
        for index, raw in enumerate(rows, start=1):
            if not is_blank_equipment(raw):
                try:
                    if self.upsert_demobbed(raw) == "added":
                        added += 1
                    else:
                        updated += 1
                except ValidationError as exc:
                    errors.append((index, str(exc)))
            if progress is not None and (index % 50 == 0 or index == total):
                progress(index, total)
        return {"added": added, "updated": updated, "errors": errors}

    def delete_many(self, records: list) -> int:
        """Permanently remove several records. Returns how many went."""
        return sum(1 for record in records if self.delete(record))

    def _log_vendor_autocreate(self, code, name):
        """Note the auto-created vendor in the EQUIPMENT log too, so the trail
        explains where that new vendor came from (the vendor master's own log
        already carries its 'Added' entry from the upsert)."""
        if self.change_log is not None:
            self.change_log.record(
                code, name, "Vendor Added",
                f"Vendor {code} auto-created in the vendor master from an equipment row",
            )

    def bulk_upsert(self, raw_records: list, progress=None) -> dict:
        """Import any number of rows. There is no row cap.

        The whole batch is applied in memory and written to disk ONCE at the
        end (and the change log likewise), so a 20,000-row upload does not do
        20,000 full-file rewrites. `progress(done, total)` is called
        periodically so the caller can drive a loading dialog.
        """
        added = updated = 0
        errors = []
        log_entries = []
        vendors_created = []
        total = len(raw_records)

        with self._lock:
            for idx, raw in enumerate(raw_records, start=1):
                if not is_blank_equipment(raw):
                    try:
                        cleaned = validate_equipment(raw)
                    except ValidationError as exc:
                        errors.append((idx, str(exc)))
                        cleaned = None
                    if cleaned is not None:
                        existing = self._find_existing(cleaned)
                        if existing is not None:
                            changes = [
                                f"{EQUIPMENT_LABELS[k]}: '{existing.get(k, '')}' -> '{cleaned[k]}'"
                                for k in EQUIPMENT_KEYS
                                if cleaned[k] and cleaned[k] != existing.get(k, "")
                            ]
                            for key in EQUIPMENT_KEYS:
                                if cleaned[key]:
                                    existing[key] = cleaned[key]
                            updated += 1
                            target = existing
                            if changes:
                                log_entries.append((
                                    equipment_id(target),
                                    target.get("equipment_description", ""),
                                    "Updated", "; ".join(changes),
                                ))
                        else:
                            self._records.append(cleaned)
                            added += 1
                            target = cleaned
                            log_entries.append((
                                equipment_id(target),
                                target.get("equipment_description", ""),
                                "Added", "New equipment record created",
                            ))
                        # Index incrementally: re-indexing the whole dataset
                        # per row would make a large import quadratic.
                        for lookup_key in EQUIPMENT_LOOKUP_KEYS:
                            value = target.get(lookup_key, "")
                            if value:
                                self._index[(lookup_key, value.lower())] = target
                        created = self._sync_vendor(target)
                        if created:
                            vendors_created.append(created)

                if progress is not None and (idx % 200 == 0 or idx == total):
                    progress(idx, total)

            if added or updated:
                self._reindex()
                self.save()

        if self.change_log is not None:
            for code, name in vendors_created:
                log_entries.append((
                    code, name, "Vendor Added",
                    f"Vendor {code} auto-created in the vendor master from an equipment row",
                ))
            if log_entries:
                self.change_log.record_many(log_entries)

        return {
            "added": added, "updated": updated, "errors": errors,
            "vendors_created": len(vendors_created),
        }

    def demob(self, identifier: str, demob_date: str) -> dict:
        """Close out one machine by any of its identifiers.

        Returns {"status": ..., "record": ...} where status is:
          "demobbed"       - the running record was closed
          "already"        - that machine is already de-mobbed
          "missing"        - no such identifier in the master
        """
        identifier = normalize(identifier)
        demob_date = normalize(demob_date)
        if not identifier:
            return {"status": "missing", "record": None}
        if not demob_date:
            raise ValidationError(EQUIPMENT_LABELS[DEMOB_FIELD], "is required to de-mob")

        with self._lock:
            record = None
            for key in EQUIPMENT_LOOKUP_KEYS:
                record = self._index.get((key, identifier.lower()))
                if record is not None:
                    break
            if record is None:
                closed = self._find_demobbed(identifier)
                return {"status": "already" if closed else "missing", "record": closed}

            record[DEMOB_FIELD] = demob_date
            self._reindex()      # drops it from the running index
            self.save()
            snapshot = dict(record)

        if self.change_log is not None:
            self.change_log.record(
                equipment_id(snapshot), snapshot.get("equipment_description", ""),
                "De-mobbed",
                f"{EQUIPMENT_LABELS[DEMOB_FIELD]} set to '{demob_date}' - record closed "
                "and locked; a later re-arrival is entered as a fresh record",
            )
        return {"status": "demobbed", "record": snapshot}

    def demob_many(self, rows: list, progress=None) -> dict:
        """De-mob a batch of (identifier, date) rows. Returns a summary."""
        demobbed, already, missing, errors = 0, [], [], []
        total = len(rows)
        for index, row in enumerate(rows, start=1):
            identifier = normalize(row.get("identifier", ""))
            date = normalize(row.get("demob_date", ""))
            if not identifier:
                continue
            try:
                outcome = self.demob(identifier, date)
            except ValidationError as exc:
                errors.append((index, str(exc)))
                continue
            if outcome["status"] == "demobbed":
                demobbed += 1
            elif outcome["status"] == "already":
                already.append(identifier)
            else:
                missing.append(identifier)
            if progress is not None and (index % 50 == 0 or index == total):
                progress(index, total)
        return {"demobbed": demobbed, "already": already, "missing": missing, "errors": errors}

    # ------------------------------------------------------- fleet views --
    def running_records(self) -> list:
        return [r for r in self._records if not is_demobbed(r)]

    def demob_records(self) -> list:
        return [r for r in self._records if is_demobbed(r)]

    def update_field(self, record: dict, key: str, value) -> bool:
        """Edit ONE cell in place (used by the editable grid). Returns True
        when the value actually changed."""
        if key not in EQUIPMENT_KEYS:
            raise KeyError(key)
        if is_demobbed(record) and key != DEMOB_FIELD:
            raise ValidationError(
                EQUIPMENT_LABELS[key],
                "cannot be edited - this machine is de-mobbed and its record is closed. "
                "If it has returned to site, add it again as a new record.",
            )
        new_value = normalize(value)
        old_value = record.get(key, "")
        if new_value == old_value:
            return False
        if key in EQUIPMENT_NUMERIC_FIELDS and new_value and not new_value.isdigit():
            raise ValidationError(EQUIPMENT_LABELS[key], "must be a number")

        with self._lock:
            record[key] = new_value
            self._reindex()
            self.save()
            created_vendor = self._sync_vendor(record) if key in ("vendor_code", "vendor_name") else None

        if self.change_log is not None:
            self.change_log.record(
                equipment_id(record), record.get("equipment_description", ""),
                "Updated", f"{EQUIPMENT_LABELS[key]}: '{old_value}' -> '{new_value}'",
            )
        if created_vendor:
            self._log_vendor_autocreate(*created_vendor)
        return True

    def delete(self, record: dict) -> bool:
        removed = None
        with self._lock:
            for i, existing in enumerate(self._records):
                if existing is record or all(
                    existing.get(k) == record.get(k) for k in EQUIPMENT_KEYS
                ):
                    removed = self._records.pop(i)
                    self._reindex()
                    self.save()
                    break
        if removed is None:
            return False
        if self.change_log is not None:
            self.change_log.record(
                equipment_id(removed), removed.get("equipment_description", ""),
                "Deleted", "Equipment record permanently deleted",
            )
        return True

    def clear(self):
        with self._lock:
            self._records = []
            self._reindex()
            self.save()

    # ------------------------------------------------------------- Reads --
    def lookup(self, identifier: str, include_demobbed: bool = True):
        """Find one machine by ANY of RH/RO Number, Technical ID or Reg No.

        The RUNNING record wins - that is the machine currently on site. A
        closed record is only returned when nothing is running under that
        identifier (and `include_demobbed` allows it).
        """
        value = normalize(identifier).lower()
        if not value:
            return None
        for key in EQUIPMENT_LOOKUP_KEYS:
            found = self._index.get((key, value))
            if found is not None:
                return found
        return self._find_demobbed(identifier) if include_demobbed else None

    def lookup_many(self, identifiers: list):
        """Resolve many identifiers, preserving input order and skipping
        duplicates. Returns (found_records, missing_identifiers)."""
        found, missing, seen = [], [], set()
        for raw in identifiers:
            value = normalize(raw)
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            record = self.lookup(value)
            if record is not None:
                found.append(record)
            else:
                missing.append(value)
        return found, missing

    def all_records(self) -> list:
        return list(self._records)

    def search(self, query: str) -> list:
        """Substring match across every field - the equipment list is browsed
        by description/plant/vendor as often as by exact identifier."""
        q = normalize(query).lower()
        if not q:
            return self.all_records()
        return [
            r for r in self._records
            if any(q in str(r.get(k, "")).lower() for k in EQUIPMENT_KEYS)
        ]

    def for_vendor(self, vendor_code: str) -> list:
        code = normalize(vendor_code)
        return [r for r in self._records if r.get("vendor_code") == code]

    def __len__(self):
        return len(self._records)
