import json
import os
import threading

from .logger import base_dir

_LOCK = threading.Lock()

DEFAULTS = {
    "exclusions": [],
    "password_hash": None,
    "password_salt": None,
    "auto_clean_on_exit": False,
    "auto_interval_min": 0,
    "hotkey_enabled": True,
    "panic_mode": "recycle",
    "self_purge_on_exit": False,
    "hosts_block": False,
    "ui_mode": "claro",
    "float_visible": False,
    "float_x": None,
    "float_y": None,
}


class SettingsStore:
    def __init__(self):
        self._path = os.path.join(base_dir(), "config.json")
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            self._data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def save(self):
        with _LOCK:
            try:
                with open(self._path, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2)
            except OSError:
                pass

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key]
        return DEFAULTS.get(key, default)

    def set(self, key, value):
        with _LOCK:
            self._data[key] = value
        self.save()


_store = None


def get_settings():
    global _store
    if _store is None:
        _store = SettingsStore()
    return _store
