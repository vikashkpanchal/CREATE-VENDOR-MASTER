"""Small persisted app preferences.

Holds the CC addresses applied to outgoing email. Each communication flow
keeps its OWN CC row - the people copied on a defective-invoice chase are
rarely the people copied on an equipment breakdown - so each is asked for
once, stored in data/app_settings.json, and reused from then on.
"""

import json
import os
import threading

from vendor_app.config import CC_BREAKDOWN_KEY, CC_DEFECTIVE_KEY, SETTINGS_FILE

DEFAULTS = {
    # Legacy single CC, kept so an existing settings file still opens; it
    # seeds both per-flow rows the first time this version runs.
    "cc_email": "",
    "cc_email_prompted": False,
    CC_DEFECTIVE_KEY: "",
    f"{CC_DEFECTIVE_KEY}_prompted": False,
    CC_BREAKDOWN_KEY: "",
    f"{CC_BREAKDOWN_KEY}_prompted": False,
}

CC_KEYS = (CC_DEFECTIVE_KEY, CC_BREAKDOWN_KEY)


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
        self._migrate_legacy_cc()

    def _migrate_legacy_cc(self):
        """Carry a pre-split CC address across to both flows.

        Someone upgrading should not be asked again for an address they have
        already given, and should not silently lose it either - so the old
        single value becomes the starting point for both rows, and stays
        editable independently from then on.
        """
        legacy = (self._data.get("cc_email") or "").strip()
        legacy_prompted = bool(self._data.get("cc_email_prompted"))
        if not legacy and not legacy_prompted:
            return
        changed = False
        for key in CC_KEYS:
            if not self._data.get(key) and not self._data.get(f"{key}_prompted"):
                self._data[key] = legacy
                self._data[f"{key}_prompted"] = legacy_prompted
                changed = True
        if changed:
            self.save()

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

    # ---------------------------------------------------------- CC email --
    def cc_for(self, key: str) -> str:
        """The CC address for one flow (CC_DEFECTIVE_KEY / CC_BREAKDOWN_KEY)."""
        return self._data.get(key, "")

    def set_cc_for(self, key: str, value: str):
        with self._lock:
            self._data[key] = (value or "").strip()
            self._data[f"{key}_prompted"] = True
            self.save()

    def cc_prompted_for(self, key: str) -> bool:
        """True once the user has been asked for THIS flow's CC address, even
        if they left it blank - so we never nag them a second time."""
        return bool(self._data.get(f"{key}_prompted", False))

    # Backwards-compatible single-CC view, still used by anything that has
    # not been told which flow it belongs to.
    @property
    def cc_email(self) -> str:
        return self._data.get(CC_DEFECTIVE_KEY, "")

    def set_cc_email(self, value: str):
        self.set_cc_for(CC_DEFECTIVE_KEY, value)

    @property
    def cc_prompted(self) -> bool:
        return self.cc_prompted_for(CC_DEFECTIVE_KEY)
