import json
import os
import time

from .paths import expand


def base_dir():
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
