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
        cleaned = validate_record(raw_record)
        code = cleaned["vendor_code"]
        now = _now()

        with self._lock:
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
                result = "updated"
                vendor_name_for_log = existing.get("vendor_name", "")
            else:
                cleaned["status"] = status if status in STATUS_VALUES else STATUS_DEFAULT
                cleaned["created_at"] = now
                cleaned["updated_at"] = now
                self._records[code] = cleaned
                self._order.append(code)
                result = "added"
                changes = None
                vendor_name_for_log = cleaned.get("vendor_name", "")
            self.save()

        if self.audit_log is not None:
            if result == "added":
                self.audit_log.record(code, vendor_name_for_log, "Added", "New vendor record created")
            elif changes:
                self.audit_log.record(code, vendor_name_for_log, "Updated", "; ".join(changes))
        return result

    def bulk_upsert(self, raw_records: list) -> dict:
        """Upsert a batch of raw records (e.g. from the bulk-entry grid).

        Blank rows are silently skipped. Each failure is collected instead
        of aborting the whole batch, so a typo in row 42 never loses the
        other 99 rows.
        """
        added = updated = 0
        errors = []
        for idx, raw in enumerate(raw_records, start=1):
            if is_blank_record(raw):
                continue
            try:
                result = self.upsert(raw)
                if result == "added":
                    added += 1
                else:
                    updated += 1
            except ValidationError as exc:
                errors.append((idx, str(exc)))
        return {"added": added, "updated": updated, "errors": errors}

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
        and optionally by lifecycle status ("All" or None means no filter)."""
        records = self.all_records()
        if status and status != "All":
            records = [r for r in records if r.get("status", STATUS_DEFAULT) == status]
        q = normalize(query).lower()
        if not q:
            return records
        return [
            r for r in records
            if q in r["vendor_code"].lower() or q in r["vendor_name"].lower()
        ]

    def __len__(self):
        return len(self._order)
