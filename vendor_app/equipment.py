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

    def __init__(self, path: str = EQUIPMENT_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._records = []           # list of cleaned dicts, display order
        self._index = {}             # (lookup_key, value.lower()) -> record
        self.load()

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
                for key in EQUIPMENT_KEYS:
                    if cleaned[key]:
                        existing[key] = cleaned[key]
                result = "updated"
            else:
                self._records.append(cleaned)
                result = "added"
            self._reindex()
            self.save()
        return result

    def bulk_upsert(self, raw_records: list) -> dict:
        added = updated = 0
        errors = []
        with self._lock:
            for idx, raw in enumerate(raw_records, start=1):
                if is_blank_equipment(raw):
                    continue
                try:
                    cleaned = validate_equipment(raw)
                except ValidationError as exc:
                    errors.append((idx, str(exc)))
                    continue
                existing = self._find_existing(cleaned)
                if existing is not None:
                    for key in EQUIPMENT_KEYS:
                        if cleaned[key]:
                            existing[key] = cleaned[key]
                    updated += 1
                else:
                    self._records.append(cleaned)
                    added += 1
                self._reindex()
            if added or updated:
                self.save()
        return {"added": added, "updated": updated, "errors": errors}

    def delete(self, record: dict) -> bool:
        with self._lock:
            for i, existing in enumerate(self._records):
                if existing is record or all(
                    existing.get(k) == record.get(k) for k in EQUIPMENT_KEYS
                ):
                    del self._records[i]
                    self._reindex()
                    self.save()
                    return True
        return False

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
