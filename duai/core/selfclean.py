import os
import shutil

from ..utils.logger import base_dir, logs_dir
from ..utils.paths import iter_paths, delete_filesystem


def purge_logs(log_file=None):
    path = log_file or os.path.join(logs_dir(), "duai.log")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("")
        return True
    except OSError:
        return False


def purge_own_recent_links():
    removed = 0
    for link in iter_paths("%APPDATA%/Microsoft/Windows/Recent/*.lnk"):
        name = os.path.splitext(os.path.basename(link))[0].lower()
        if "duai" in name or "du-ai" in name:
            if delete_filesystem(link, permanent=True):
                removed += 1
    return removed


def purge_all_local_data(confirm_base=None):
    target = confirm_base or base_dir()
    if os.path.normpath(target) != os.path.normpath(base_dir()):
        raise ValueError("ruta invalida")
    shutil.rmtree(target, ignore_errors=True)
    return not os.path.exists(target)
