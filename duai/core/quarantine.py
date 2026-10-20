"""Quarantine module for duAI - Safe isolation with integrity verification."""

import hashlib
import json
import os
import time
import uuid
from typing import Optional

from ..utils.logger import base_dir
from ..utils.paths import expand


def quarantine_dir():
    path = os.path.join(base_dir(), "quarantine")
    os.makedirs(path, exist_ok=True)
    return path


def manifest_path():
    return os.path.join(quarantine_dir(), "manifest.json")


def _load_manifest() -> dict:
    """Load manifest with validation and migration support."""
    path = manifest_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        # Try backup
        backup_path = path + ".bak"
        try:
            with open(backup_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}

    # Validate structure and migrate if needed
    if not isinstance(data, dict):
        return {}

    validated = {}
    for token, info in data.items():
        if not isinstance(info, dict):
            continue
        validated[token] = {
            "original": info.get("original", ""),
            "stored": info.get("stored", ""),
            "size": info.get("size", 0),
            "hash": info.get("hash"),
            "timestamp": info.get("timestamp", 0),
            "version": info.get("version", 1)
        }

    return validated


def _save_manifest(manifest: dict):
    """Atomic manifest write with backup."""
    manifest_file = manifest_path()
    temp_file = manifest_file + ".tmp"
    backup_file = manifest_file + ".bak"

    try:
        # Write to temp file first
        with open(temp_file, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        # Create backup of existing
        if os.path.exists(manifest_file):
            os.replace(manifest_file, backup_file)

        # Atomic replace
        os.replace(temp_file, manifest_file)

        # Remove backup on success
        if os.path.exists(backup_file):
            os.remove(backup_file)
    except OSError:
        # Cleanup temp file
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        # Restore backup if exists
        if os.path.exists(backup_file):
            try:
                os.replace(backup_file, manifest_file)
            except OSError:
                pass


def _calculate_hash(filepath: str) -> Optional[str]:
    """Calculate SHA256 hash for integrity verification."""
    if not os.path.isfile(filepath):
        return None
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except OSError:
        return None


def quarantine_path(path: str, base: Optional[str] = None) -> tuple[bool, str]:
    """Move a file/directory to quarantine with integrity hash.
    
    Returns:
        (success: bool, token_or_error: str)
    """
    qdir = base or quarantine_dir()
    os.makedirs(qdir, exist_ok=True)
    
    manifest = _load_manifest() if base is None else {}
    token = uuid.uuid4().hex[:8]
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in os.path.basename(path))[:80]
    dest = os.path.join(qdir, f"{token}__{safe_name}")

    # Calculate hash BEFORE moving for integrity verification
    file_hash = None
    file_size = 0
    if os.path.isfile(path):
        try:
            file_size = os.path.getsize(path)
            file_hash = _calculate_hash(path)
        except OSError:
            pass

    try:
        # Atomic move using os.replace (atomic on same filesystem)
        os.replace(path, dest)
    except OSError:
        import shutil
        try:
            shutil.move(path, dest)
        except (OSError, shutil.Error) as e:
            return False, str(e)

    if base is None:
        manifest[token] = {
            "original": os.path.abspath(path),
            "stored": dest,
            "size": file_size,
            "hash": file_hash,
            "timestamp": time.time(),
            "version": 1
        }
        _save_manifest(manifest)

    return True, token


def quarantined_items() -> list[dict]:
    """Get list of all quarantined items with metadata."""
    manifest = _load_manifest()
    items = []
    for token, info in manifest.items():
        stored = info.get("stored", "")
        exists = os.path.exists(stored)
        items.append({
            "token": token,
            "original": info["original"],
            "stored": stored,
            "size": info.get("size", 0),
            "hash": info.get("hash"),
            "timestamp": info.get("timestamp", 0),
            "available": exists
        })
    return items


def restore_item(token: str, base: Optional[str] = None) -> tuple[bool, str]:
    """Restore a single quarantined item by token.
    
    Returns:
        (success: bool, destination_path_or_error: str)
    """
    manifest = _load_manifest()
    if token not in manifest:
        return False, "Token not found in manifest"

    info = manifest[token]
    stored = info.get("stored", "")
    original = info.get("original", "")

    if not stored or not os.path.exists(stored):
        return False, "Quarantined file not found"

    # Verify integrity if hash exists
    if info.get("hash"):
        current_hash = _calculate_hash(stored)
        if current_hash != info["hash"]:
            return False, "Integrity check failed - file corrupted"

    parent = os.path.dirname(original)
    if not os.path.isdir(parent):
        parent = expand("%USERPROFILE%/duAI_restaurado")
        os.makedirs(parent, exist_ok=True)

    dest = os.path.join(parent, os.path.basename(original))

    # Handle name conflicts
    counter = 1
    base_dest = dest
    while os.path.exists(dest):
        name, ext = os.path.splitext(base_dest)
        dest = f"{name}_{counter}{ext}"
        counter += 1

    try:
        os.replace(stored, dest)
    except OSError:
        import shutil
        try:
            shutil.move(stored, dest)
        except (OSError, shutil.Error) as e:
            return False, str(e)

    # Update manifest
    manifest.pop(token, None)
    _save_manifest(manifest)
    return True, dest


def restore_all(base: Optional[str] = None) -> int:
    """Restore all quarantined items."""
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
            os.replace(stored, dest)
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


def purge_quarantine(base: Optional[str] = None) -> int:
    """Permanently delete all quarantined items."""
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


def get_quarantine_stats(base: Optional[str] = None) -> dict:
    """Get detailed quarantine storage statistics."""
    qdir = base or quarantine_dir()
    manifest = _load_manifest()

    stats = {
        "item_count": len(manifest),
        "total_size": 0,
        "by_age": {"<1d": 0, "1-7d": 0, "1-30d": 0, ">30d": 0},
        "by_extension": {},
        "disk_usage": 0,
        "disk_free": 0,
        "disk_total": 0,
        "manifest_size": 0
    }

    now = time.time()
    for token, info in manifest.items():
        size = info.get("size", 0)
        stats["total_size"] += size

        # Age distribution
        age_days = (now - info.get("timestamp", now)) / 86400
        if age_days < 1:
            stats["by_age"]["<1d"] += size
        elif age_days < 7:
            stats["by_age"]["1-7d"] += size
        elif age_days < 30:
            stats["by_age"]["1-30d"] += size
        else:
            stats["by_age"][">30d"] += size

        # Extension breakdown
        ext = os.path.splitext(info.get("original", ""))[1].lower() or "no_ext"
        stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + size

    # Actual disk usage
    try:
        import psutil
        usage = psutil.disk_usage(qdir)
        stats["disk_usage"] = usage.used
        stats["disk_free"] = usage.free
        stats["disk_total"] = usage.total
    except (OSError, ImportError):
        pass

    # Manifest size
    try:
        stats["manifest_size"] = os.path.getsize(manifest_path())
    except OSError:
        pass

    return stats


def verify_quarantine_integrity(base: Optional[str] = None) -> dict:
    """Verify all quarantined files match their recorded hashes."""
    manifest = _load_manifest()
    results = {
        "total": len(manifest),
        "verified": 0,
        "corrupted": 0,
        "missing": 0,
        "errors": []
    }

    for token, info in manifest.items():
        stored = info.get("stored", "")
        expected_hash = info.get("hash")

        if not os.path.exists(stored):
            results["missing"] += 1
            results["errors"].append({"token": token, "issue": "File missing from quarantine"})
            continue

        if expected_hash:
            try:
                actual_hash = _calculate_hash(stored)
                if actual_hash == expected_hash:
                    results["verified"] += 1
                else:
                    results["corrupted"] += 1
                    results["errors"].append({
                        "token": token,
                        "issue": "Hash mismatch - file corrupted",
                        "expected": expected_hash,
                        "actual": actual_hash
                    })
            except OSError as e:
                results["corrupted"] += 1
                results["errors"].append({"token": token, "issue": f"Cannot read file: {e}"})
        else:
            # No hash recorded (legacy), just check file exists
            results["verified"] += 1

    return results


def get_undo_info() -> dict:
    """Get information needed for undo operations."""
    manifest = _load_manifest()
    total_size = sum(info.get("size", 0) for info in manifest.values())
    return {
        "item_count": len(manifest),
        "total_size": total_size,
        "items": [
            {
                "token": token,
                "original": info["original"],
                "size": info.get("size", 0),
                "timestamp": info.get("timestamp", 0),
                "age_days": (time.time() - info.get("timestamp", 0)) / 86400
            }
            for token, info in manifest.items()
        ]
    }