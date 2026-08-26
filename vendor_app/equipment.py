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
    DATA_DIR,
    EQUIPMENT_FILE,
    EQUIPMENT_KEYS,
    EQUIPMENT_LABELS,
    EQUIPMENT_LOOKUP_KEYS,
    EQUIPMENT_NUMERIC_FIELDS,
)
from vendor_app.validators import ValidationError, normalize


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
        """Rebuild the identifier -> record index. Later rows win on a clash,
        matching 'last write wins' upsert behaviour."""
        self._index = {}
        for record in self._records:
            for key in EQUIPMENT_LOOKUP_KEYS:
                value = record.get(key, "")
                if value:
                    self._index[(key, value.lower())] = record

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        df = pd.DataFrame(self._records, columns=EQUIPMENT_KEYS)
        df.to_csv(self.path, index=False)

    # ------------------------------------------------------------ Writes --
    def _find_existing(self, cleaned: dict):
        for key in EQUIPMENT_LOOKUP_KEYS:
            value = cleaned.get(key, "")
            if value:
                found = self._index.get((key, value.lower()))
                if found is not None:
                    return found
        return None

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

    def update_field(self, record: dict, key: str, value) -> bool:
        """Edit ONE cell in place (used by the editable grid). Returns True
        when the value actually changed."""
        if key not in EQUIPMENT_KEYS:
            raise KeyError(key)
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
    def lookup(self, identifier: str):
        """Find one machine by ANY of RH/RO Number, Technical ID or Reg No."""
        value = normalize(identifier).lower()
        if not value:
            return None
        for key in EQUIPMENT_LOOKUP_KEYS:
            found = self._index.get((key, value))
            if found is not None:
                return found
        return None

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
