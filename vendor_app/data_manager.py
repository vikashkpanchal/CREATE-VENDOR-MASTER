"""In-memory + on-disk vendor record store with cell-level upsert semantics,
vendor lifecycle status, and a wired-in audit trail.

Persistence uses a plain CSV under data/ as the internal store (fast,
dependency-light, diff-friendly). The user-facing ".xlsx" files are only
ever produced on demand via export.py.
"""

import os
import threading
from datetime import datetime

import pandas as pd

from vendor_app.config import DATA_FILE, DATA_DIR, KEYS, LABELS, STORE_FIELDS, STATUS_DEFAULT, STATUS_VALUES
from vendor_app.validators import ValidationError, validate_record, normalize, is_blank_record


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class VendorStore:
    """Thread-safe CRUD + search over the vendor master dataset."""

    def __init__(self, path: str = DATA_FILE, audit_log=None):
        self.path = path
        self.audit_log = audit_log
        self._lock = threading.Lock()
        self._records = {}   # vendor_code -> cleaned record dict (KEYS + status/created_at/updated_at)
        self._order = []     # vendor_code insertion order (stable display order)
        self.load()

    # ---------------------------------------------------------------- IO --
    def load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._records = {}
        self._order = []
        if os.path.exists(self.path):
            df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            for _, row in df.iterrows():
                code = normalize(row.get("vendor_code", ""))
                if not code:
                    continue
                record = {k: normalize(row.get(k, "")) for k in KEYS}
                record["vendor_code"] = code
                record["status"] = normalize(row.get("status", "")) or STATUS_DEFAULT
                record["created_at"] = normalize(row.get("created_at", ""))
                record["updated_at"] = normalize(row.get("updated_at", ""))
                self._records[code] = record
                self._order.append(code)

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        rows = [self._records[code] for code in self._order]
        df = pd.DataFrame(rows, columns=STORE_FIELDS)
        df.to_csv(self.path, index=False)

    # ------------------------------------------------------------ Writes --
    def _apply_upsert(self, raw_record: dict, status: str = None):
        """Validate + merge `raw_record` into memory ONLY - no disk write,
        no audit call. Shared by upsert() (single write, saves once) and
        bulk_upsert() (many writes, saves once at the end) so a 100-row
        grid save doesn't rewrite the entire CSV 100 times.

        Returns (result, audit_action, audit_details, vendor_name), where
        audit_action/audit_details are None if nothing actually changed
        (e.g. an update with no non-blank fields and no status change).
        Caller must hold self._lock.
        """
        cleaned = validate_record(raw_record)
        code = cleaned["vendor_code"]
        now = _now()

        if code in self._records:
            existing = self._records[code]
            changes = []
            for key in KEYS:
                if key == "vendor_code":
                    continue
                if cleaned[key] and cleaned[key] != existing.get(key, ""):
                    changes.append(f"{LABELS[key]}: '{existing.get(key, '')}' -> '{cleaned[key]}'")
                    existing[key] = cleaned[key]
            if status and status in STATUS_VALUES and status != existing.get("status"):
                changes.append(f"Status: '{existing.get('status', STATUS_DEFAULT)}' -> '{status}'")
                existing["status"] = status
            if changes:
                existing["updated_at"] = now
            audit_action = "Updated" if changes else None
            audit_details = "; ".join(changes) if changes else None
            return "updated", audit_action, audit_details, existing.get("vendor_name", "")

        cleaned["status"] = status if status in STATUS_VALUES else STATUS_DEFAULT
        cleaned["created_at"] = now
        cleaned["updated_at"] = now
        self._records[code] = cleaned
        self._order.append(code)
        return "added", "Added", "New vendor record created", cleaned.get("vendor_name", "")

    def upsert(self, raw_record: dict, status: str = None) -> str:
        """Validate `raw_record` and insert/merge it by Vendor Code.

        Cell-level partial merge: when the vendor already exists, only
        non-blank fields in `raw_record` overwrite existing values; blank
        cells leave previously stored data untouched. Vendor Code itself is
        never altered by a merge (it is the key). `status`, if given,
        additionally sets the vendor's lifecycle status in the same write.

        Every write is recorded to the audit trail with a field-level diff.
        Returns "added" or "updated".
        """
        with self._lock:
            code = normalize(raw_record.get("vendor_code", ""))
            result, audit_action, audit_details, vendor_name = self._apply_upsert(raw_record, status)
            self.save()

        if self.audit_log is not None and audit_action:
            self.audit_log.record(code, vendor_name, audit_action, audit_details)
        return result

    def bulk_upsert(self, raw_records: list, progress=None) -> dict:
        """Upsert a batch of raw records (e.g. from the bulk-entry grid).

        Blank rows are silently skipped. Each failure is collected instead
        of aborting the whole batch, so a typo in row 42 never loses the
        other 99 rows. The dataset is written to disk once at the end
        (not once per row) so a 100-row save stays fast even against a
        large existing master.
        """
        added = updated = 0
        errors = []
        audit_entries = []  # (vendor_code, vendor_name, action, details)

        total = len(raw_records)
        with self._lock:
            for idx, raw in enumerate(raw_records, start=1):
                if progress is not None and (idx % 200 == 0 or idx == total):
                    progress(idx, total)
                if is_blank_record(raw):
                    continue
                try:
                    code = normalize(raw.get("vendor_code", ""))
                    result, audit_action, audit_details, vendor_name = self._apply_upsert(raw)
                    if result == "added":
                        added += 1
                    else:
                        updated += 1
                    if audit_action:
                        audit_entries.append((code, vendor_name, audit_action, audit_details))
                except ValidationError as exc:
                    errors.append((idx, str(exc)))
            if added or updated:
                self.save()

        if self.audit_log is not None and audit_entries:
            self.audit_log.record_many(audit_entries)

        return {"added": added, "updated": updated, "errors": errors}

    def update_field(self, code: str, key: str, value) -> bool:
        """Edit ONE cell in place (used by the editable master grid).

        Returns True when the value actually changed. Vendor Code is the
        primary key and is never editable this way.
        """
        code = normalize(code)
        if key == "vendor_code":
            raise ValidationError(LABELS["vendor_code"], "cannot be changed")
        if key == "status":
            return self.set_status(code, normalize(value))
        if key not in KEYS:
            raise KeyError(key)

        record = self._records.get(code)
        if record is None:
            return False
        # Reuse the field rules the edit dialog and import path already use.
        cleaned = validate_record({**{k: record.get(k, "") for k in KEYS}, key: value})
        new_value, old_value = cleaned[key], record.get(key, "")
        if new_value == old_value:
            return False

        with self._lock:
            record[key] = new_value
            record["updated_at"] = _now()
            self.save()
            vendor_name = record.get("vendor_name", "")

        if self.audit_log is not None:
            self.audit_log.record(
                code, vendor_name, "Updated",
                f"{LABELS[key]}: '{old_value}' -> '{new_value}'",
            )
        return True

    def set_status(self, code: str, status: str) -> bool:
        """Change only a vendor's lifecycle status (Active/Inactive/Blocked)."""
        code = normalize(code)
        if status not in STATUS_VALUES:
            raise ValueError(f"Unknown status: {status}")
        with self._lock:
            record = self._records.get(code)
            if not record:
                return False
            old = record.get("status", STATUS_DEFAULT)
            if old == status:
                return True
            record["status"] = status
            record["updated_at"] = _now()
            self.save()
            vendor_name = record.get("vendor_name", "")
        if self.audit_log is not None:
            self.audit_log.record(code, vendor_name, "Status Change", f"Status: '{old}' -> '{status}'")
        return True

    def delete(self, code: str) -> bool:
        """Permanently remove a vendor record. Irreversible - prefer set_status
        to Inactive/Blocked for reversible lifecycle changes."""
        code = normalize(code)
        with self._lock:
            if code not in self._records:
                return False
            record = self._records.pop(code)
            self._order.remove(code)
            self.save()
        if self.audit_log is not None:
            self.audit_log.record(
                code, record.get("vendor_name", ""), "Deleted", "Vendor record permanently deleted"
            )
        return True

    # ------------------------------------------------------------- Reads --
    def get(self, code: str):
        return self._records.get(normalize(code))

    def get_many(self, codes: list):
        """Look up multiple vendor codes, preserving requested order.

        Returns (found_records, missing_codes).
        """
        found, missing = [], []
        for raw_code in codes:
            code = normalize(raw_code)
            if not code:
                continue
            record = self._records.get(code)
            if record:
                found.append(record)
            else:
                missing.append(code)
        return found, missing

    def all_records(self) -> list:
        return [self._records[code] for code in self._order]

    def search(self, query: str, status: str = None) -> list:
        """Filter records by substring match on Vendor Code or Vendor Name,
        and optionally by lifecycle status ("All" or None means no filter).

        Vendor Type matches too, but only on the whole word: a substring
        match would make every search containing "ca" drag in every CAD
        vendor, which is not what someone typing a name is asking for.
        """
        records = self.all_records()
        if status and status != "All":
            records = [r for r in records if r.get("status", STATUS_DEFAULT) == status]
        q = normalize(query).lower()
        if not q:
            return records
        return [
            r for r in records
            if q in r["vendor_code"].lower()
            or q in r["vendor_name"].lower()
            or q == r.get("vendor_type", "").lower()
        ]

    def __len__(self):
        return len(self._order)
