import json
import os
import uuid

from ..utils.logger import base_dir
from ..utils.paths import expand


def quarantine_dir():
    path = os.path.join(base_dir(), "quarantine")
    os.makedirs(path, exist_ok=True)
    return path


def manifest_path():
    return os.path.join(quarantine_dir(), "manifest.json")


def _load_manifest():
    try:
        with open(manifest_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_manifest(manifest):
    try:
        with open(manifest_path(), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


def quarantine_path(path, base=None):
    qdir = base or quarantine_dir()
    os.makedirs(qdir, exist_ok=True)
    manifest = _load_manifest() if base is None else {}
    token = uuid.uuid4().hex[:8]
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in os.path.basename(path))[:80]
    dest = os.path.join(qdir, f"{token}__{safe_name}")
    try:
        os.rename(path, dest)
    except OSError:
        import shutil

        try:
            shutil.move(path, dest)
        except (OSError, shutil.Error):
            return False
    if base is None:
        manifest[token] = {"original": os.path.abspath(path), "stored": dest}
        _save_manifest(manifest)
    return True


def quarantined_items():
    manifest = _load_manifest()
    items = []
    for token, info in manifest.items():
        exists = os.path.exists(info.get("stored", ""))
        items.append({"token": token, "original": info["original"], "stored": info["stored"], "available": exists})
    return items


def restore_all(base=None):
    manifest = _load_manifest()
    restored = 0
    remaining = dict(manifest)
    for token, info in manifest.items():
        stored = info.get("stored", "")
        original = info.get("original", "")
        if not stored or not os.path.exists(stored):
            continue
        parent = os.path.dirname(original)
        if not os.path.isdir(parent):
            parent = expand("%USERPROFILE%/duAI_restaurado")
            os.makedirs(parent, exist_ok=True)
        dest = os.path.join(parent, os.path.basename(original))
        try:
            os.rename(stored, dest)
        except OSError:
            import shutil

            try:
                shutil.move(stored, dest)
            except (OSError, shutil.Error):
                continue
        remaining.pop(token, None)
        restored += 1
    _save_manifest(remaining)
    return restored


def purge_quarantine(base=None):
    removed = 0
    qdir = base or quarantine_dir()
    if not os.path.isdir(qdir):
        return 0
    for name in os.listdir(qdir):
        if name == "manifest.json":
            continue
        full = os.path.join(qdir, name)
        try:
            if os.path.isdir(full):
                import shutil

                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)
            removed += 1
        except OSError:
            pass
    _save_manifest({})
    return removed
