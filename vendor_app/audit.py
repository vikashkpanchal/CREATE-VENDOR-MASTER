"""Append-only change history (SAP-style "change documents").

One reusable ChangeLog drives both masters - the vendor master and the
equipment master each own their own log file and column set, so each tab
shows only its own history and each exports cleanly on its own.

Every add, field-level update, status change and delete performed through
a store is recorded here with a timestamp, a human-readable before/after
summary, and who made the change.
"""

import csv
import getpass
import os
import threading
from datetime import datetime

from vendor_app.config import AUDIT_COLUMNS, AUDIT_FILE


def current_actor() -> str:
    try:
        return getpass.getuser() or "local-user"
    except Exception:
        return "local-user"


class ChangeLog:
    """Append-only log. `columns` names the CSV columns; the second and third
    are the record's key and display name, whatever the entity calls them."""

    def __init__(self, path: str, columns=None):
        self.path = path
        self.columns = list(columns or AUDIT_COLUMNS)
        self._key_col = self.columns[1]
        self._name_col = self.columns[2]
        self._lock = threading.Lock()
        self._entries = []  # oldest first
        self.load()

    def load(self):
        self._entries = []
        if os.path.exists(self.path):
            with open(self.path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    self._entries.append({col: row.get(col, "") for col in self.columns})

    def _make_entry(self, key: str, name: str, action: str, details: str) -> dict:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self._key_col: key,
            self._name_col: name,
            "action": action,
            "details": details,
            "actor": current_actor(),
        }

    def record(self, key: str, name: str, action: str, details: str) -> dict:
        entry = self._make_entry(key, name, action, details)
        with self._lock:
            self._entries.append(entry)
            self._append_to_disk([entry])
        return entry

    def record_many(self, records: list) -> list:
        """Append several entries in ONE disk write. `records` is a list of
        (key, name, action, details) tuples - used by bulk imports so a
        10,000-row upload opens the log file once, not 10,000 times."""
        entries = [self._make_entry(*r) for r in records]
        if not entries:
            return entries
        with self._lock:
            self._entries.extend(entries)
            self._append_to_disk(entries)
        return entries

    def _append_to_disk(self, entries: list):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        write_header = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.columns)
            if write_header:
                writer.writeheader()
            writer.writerows(entries)

    # ------------------------------------------------------------- Reads --
    def all_entries(self) -> list:
        """Most-recent-first, as a change log is read newest-on-top."""
        return list(reversed(self._entries))

    def for_key(self, key: str) -> list:
        return [e for e in reversed(self._entries) if e.get(self._key_col) == key]

    # Backwards-compatible alias from when this only served the vendor master.
    def for_vendor(self, vendor_code: str) -> list:
        return self.for_key(vendor_code)

    def __len__(self):
        return len(self._entries)


class AuditLog(ChangeLog):
    """The vendor master's change log (kept as a named class for clarity)."""

    def __init__(self, path: str = AUDIT_FILE):
        super().__init__(path, AUDIT_COLUMNS)
