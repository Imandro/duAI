import json
import os
import time

from .paths import expand

_portable_mode = False


def set_portable_mode(enabled: bool):
    """Activa el modo portable: base_dir apunta junto al ejecutable, no a %LOCALAPPDATA%."""
    global _portable_mode
    _portable_mode = bool(enabled)


def is_portable_mode() -> bool:
    return _portable_mode


def base_dir():
    if _portable_mode:
        # Modo portable: configuración junto al ejecutable (ideal para USB)
        if getattr(os.sys if hasattr(os, "sys") else __import__("sys"), "frozen", False):
            import sys

            base = os.path.dirname(sys.executable)
        else:
            import sys

            base = os.path.dirname(os.path.abspath(sys.argv[0] or __file__))
        path = os.path.join(base, "duAI_data")
    else:
        path = expand("%LOCALAPPDATA%/duAI")
    os.makedirs(path, exist_ok=True)
    return path


def logs_dir():
    path = os.path.join(base_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def log(event, **data):
    entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event}
    entry.update(data)
    try:
        with open(os.path.join(logs_dir(), "duai.log"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def open_logs_folder():
    os.startfile(logs_dir())
