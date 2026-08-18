"""In-memory + on-disk vendor record store with cell-level upsert semantics.

Persistence uses a plain CSV under data/ as the internal store (fast,
dependency-light, diff-friendly). The user-facing ".xlsx" files are only
ever produced on demand via export.py.
"""

import os
import threading

import pandas as pd

from vendor_app.config import DATA_FILE, DATA_DIR, KEYS
from vendor_app.validators import ValidationError, validate_record, normalize, is_blank_record


class VendorStore:
    """Thread-safe CRUD + search over the vendor master dataset."""

    def __init__(self, path: str = DATA_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._records = {}   # vendor_code -> cleaned record dict
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
                self._records[code] = record
                self._order.append(code)

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        rows = [self._records[code] for code in self._order]
        df = pd.DataFrame(rows, columns=KEYS)
        df.to_csv(self.path, index=False)

    # ------------------------------------------------------------ Writes --
    def upsert(self, raw_record: dict) -> str:
        """Validate `raw_record` and insert/merge it by Vendor Code.

        Cell-level partial merge: when the vendor already exists, only
        non-blank fields in `raw_record` overwrite existing values; blank
        cells leave previously stored data untouched. Vendor Code itself is
        never altered by a merge (it is the key).

        Returns "added" or "updated".
        """
        cleaned = validate_record(raw_record)
        code = cleaned["vendor_code"]
        with self._lock:
            if code in self._records:
                existing = self._records[code]
                for key in KEYS:
                    if key == "vendor_code":
                        continue
                    if cleaned[key]:
                        existing[key] = cleaned[key]
                result = "updated"
            else:
                self._records[code] = cleaned
                self._order.append(code)
                result = "added"
            self.save()
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

    def delete(self, code: str) -> bool:
        code = normalize(code)
        with self._lock:
            if code not in self._records:
                return False
            del self._records[code]
            self._order.remove(code)
            self.save()
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

    def search(self, query: str) -> list:
        """Filter records by substring match on Vendor Code or Vendor Name."""
        q = normalize(query).lower()
        records = self.all_records()
        if not q:
            return records
        return [
            r for r in records
            if q in r["vendor_code"].lower() or q in r["vendor_name"].lower()
        ]

    def __len__(self):
        return len(self._order)
