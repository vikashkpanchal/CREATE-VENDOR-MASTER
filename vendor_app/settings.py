"""Small persisted app preferences.

Currently holds the CC address applied to every outgoing email. It is
asked for once, stored in data/app_settings.json, and reused from then on
(editable later from the Communication tab).
"""

import json
import os
import threading

from vendor_app.config import SETTINGS_FILE

DEFAULTS = {
    "cc_email": "",
    "cc_email_prompted": False,
}


class AppSettings:
    def __init__(self, path: str = SETTINGS_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    stored = json.load(fh)
                if isinstance(stored, dict):
                    self._data.update({k: stored.get(k, v) for k, v in DEFAULTS.items()})
            except (ValueError, OSError):
                # A corrupt/unreadable settings file must never stop the app
                # from starting - fall back to defaults and rewrite on save.
                self._data = dict(DEFAULTS)

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self.save()

    # ------------------------------------------------------------- CC email --
    @property
    def cc_email(self) -> str:
        return self._data.get("cc_email", "")

    def set_cc_email(self, value: str):
        with self._lock:
            self._data["cc_email"] = (value or "").strip()
            self._data["cc_email_prompted"] = True
            self.save()

    @property
    def cc_prompted(self) -> bool:
        """True once the user has been asked for a CC address, even if they
        left it blank - so we never nag them a second time."""
        return bool(self._data.get("cc_email_prompted", False))
