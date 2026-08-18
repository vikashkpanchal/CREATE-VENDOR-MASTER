"""Append-only change history for vendor records (SAP/Oracle-style "change
documents"). Every add, field update, status change and delete performed
through VendorStore is recorded here with a timestamp, a human-readable
summary of what changed, and who made the change.
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


class AuditLog:
    def __init__(self, path: str = AUDIT_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._entries = []  # oldest first
        self.load()

    def load(self):
        self._entries = []
        if os.path.exists(self.path):
            with open(self.path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    self._entries.append({col: row.get(col, "") for col in AUDIT_COLUMNS})

    def record(self, vendor_code: str, vendor_name: str, action: str, details: str) -> dict:
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vendor_code": vendor_code,
            "vendor_name": vendor_name,
            "action": action,
            "details": details,
            "actor": current_actor(),
        }
        with self._lock:
            self._entries.append(entry)
            self._append_to_disk(entry)
        return entry

    def _append_to_disk(self, entry: dict):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        write_header = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=AUDIT_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(entry)

    def all_entries(self) -> list:
        """Most-recent-first, as an audit trail is read newest-on-top."""
        return list(reversed(self._entries))

    def for_vendor(self, vendor_code: str) -> list:
        return [e for e in reversed(self._entries) if e["vendor_code"] == vendor_code]

    def __len__(self):
        return len(self._entries)
