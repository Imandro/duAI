"""Comprehensive self-clean with secure delete, backup, and verification."""

import os
import shutil
import tempfile
import time
import ctypes
from typing import List, Dict, Any, Optional
from ..utils.logger import base_dir, logs_dir
from ..utils.paths import iter_paths, delete_filesystem
from ..utils.settings import get_settings


# Windows API for secure delete
try:
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    # Define secure delete constants
    FILE_FLAG_DELETE_ON_CLOSE = 0x04000000
    DELETE = 0x00010000
except Exception:
    kernel32 = None


def _secure_delete_windows(path: str, passes: int = 3) -> bool:
    """Secure delete using Windows API (overwrite + delete)."""
    if not kernel32:
        return False
    
    try:
        # Get file size
        size = os.path.getsize(path)
        if size == 0:
            os.remove(path)
            return True
        
        # Overwrite with random data
        for _ in range(passes):
            with open(path, "wb") as f:
                f.write(os.urandom(size))
            # Flush to disk
            kernel32.FlushFileBuffers(ctypes.windll.kernel32.CreateFileW(
                path, DELETE, 0, None, 3, FILE_FLAG_DELETE_ON_CLOSE, None
            ))
        
        # Final delete
        os.remove(path)
        return True
    except Exception:
        return False


def _secure_delete_unix(path: str, passes: int = 3) -> bool:
    """Secure delete on Unix-like systems using shred."""
    import subprocess
    try:
        subprocess.run(["shred", "-n", str(passes), "-z", "-u", path], 
                      check=True, capture_output=True)
        return True
    except Exception:
        return False


def secure_delete(path: str, passes: int = 3) -> bool:
    """Securely delete a file with multiple overwrites."""
    if os.name == "nt":
        return _secure_delete_windows(path, passes)
    else:
        return _secure_delete_unix(path, passes)


def _create_self_backup(backup_dir: Optional[str] = None) -> Optional[str]:
    """Create a backup of duAI's own data before self-clean."""
    if backup_dir is None:
        backup_dir = tempfile.gettempdir()
    
    timestamp = int(time.time())
    backup_path = os.path.join(backup_dir, f"duai_self_backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    
    data_dir = base_dir()
    if not os.path.exists(data_dir):
        return None
    
    # Backup important files
    important = ["settings.json", "stats.json", "quarantine.db", "logs"]
    backed_up = []
    
    for item in important:
        src = os.path.join(data_dir, item)
        dst = os.path.join(backup_path, item)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)
            backed_up.append(item)
        except Exception:
            pass
    
    if backed_up:
        # Write manifest
        manifest = {
            "timestamp": timestamp,
            "version": "1.0",
            "items": backed_up,
            "source": data_dir,
        }
        import json
        with open(os.path.join(backup_path, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        return backup_path
    
    # Cleanup empty backup dir
    try:
        os.rmdir(backup_path)
    except Exception:
        pass
    return None


def _restore_self_backup(backup_path: str) -> bool:
    """Restore duAI data from backup."""
    if not os.path.exists(backup_path):
        return False
    
    manifest_path = os.path.join(backup_path, "manifest.json")
    if not os.path.exists(manifest_path):
        return False
    
    import json
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception:
        return False
    
    source_dir = manifest.get("source", base_dir())
    
    for item in manifest.get("items", []):
        src = os.path.join(backup_path, item)
        dst = os.path.join(source_dir, item)
        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        except Exception:
            pass
    
    return True


def purge_logs(log_file: Optional[str] = None, secure: bool = False) -> bool:
    """Purge log files."""
    path = log_file or os.path.join(logs_dir(), "duai.log")
    try:
        if secure and os.path.exists(path):
            return secure_delete(path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("")
        return True
    except OSError:
        return False


def purge_all_logs(secure: bool = False) -> int:
    """Purge all log files including rotated ones."""
    removed = 0
    log_dir = logs_dir()
    if not os.path.exists(log_dir):
        return 0
    
    for fname in os.listdir(log_dir):
        if fname.startswith("duai.log") or fname.startswith("duai-"):
            fpath = os.path.join(log_dir, fname)
            try:
                if secure:
                    if secure_delete(fpath):
                        removed += 1
                else:
                    os.remove(fpath)
                    removed += 1
            except OSError:
                pass
    return removed


def purge_own_recent_links(secure: bool = False) -> int:
    """Remove duAI-related recent links."""
    removed = 0
    for link in iter_paths("%APPDATA%/Microsoft/Windows/Recent/*.lnk"):
        name = os.path.splitext(os.path.basename(link))[0].lower()
        if "duai" in name or "du-ai" in name:
            if delete_filesystem(link, permanent=secure):
                removed += 1
            elif secure and os.path.exists(link):
                if secure_delete(link):
                    removed += 1
    return removed


def purge_prefetch(secure: bool = False) -> int:
    """Purge duAI prefetch files."""
    removed = 0
    prefetch_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Prefetch")
    if not os.path.exists(prefetch_dir):
        return 0
    
    for fname in os.listdir(prefetch_dir):
        if fname.lower().startswith("duai") and fname.lower().endswith(".pf"):
            fpath = os.path.join(prefetch_dir, fname)
            try:
                if secure:
                    if secure_delete(fpath):
                        removed += 1
                else:
                    os.remove(fpath)
                    removed += 1
            except OSError:
                pass
    return removed


def purge_temp_files(secure: bool = False) -> int:
    """Purge duAI temp files."""
    removed = 0
    temp_dir = tempfile.gettempdir()
    patterns = ["duai_*", "du-ai_*", "duAI_*"]
    
    import glob
    for pattern in patterns:
        for fpath in glob.glob(os.path.join(temp_dir, pattern)):
            try:
                if os.path.isfile(fpath):
                    if secure:
                        if secure_delete(fpath):
                            removed += 1
                    else:
                        os.remove(fpath)
                        removed += 1
                elif os.path.isdir(fpath):
                    if secure:
                        for root, dirs, files in os.walk(fpath, topdown=False):
                            for f in files:
                                secure_delete(os.path.join(root, f))
                            for d in dirs:
                                os.rmdir(os.path.join(root, d))
                        os.rmdir(fpath)
                    else:
                        shutil.rmtree(fpath, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return removed


def purge_registry_traces() -> int:
    """Purge duAI registry traces."""
    from .registry_clean import clean_registry
    result = clean_registry(ai_only=False, dry_run=False)
    return sum(result.get("removed", {}).values())


def purge_all_local_data(
    confirm_base: Optional[str] = None,
    secure: bool = False,
    create_backup: bool = True,
    backup_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Comprehensive self-clean of all duAI local data.
    
    Args:
        confirm_base: Must match base_dir() for safety
        secure: Use secure deletion
        create_backup: Create backup before cleaning
        backup_dir: Custom backup directory
    
    Returns:
        Dict with results and backup path
    """
    target = confirm_base or base_dir()
    if os.path.normpath(target) != os.path.normpath(base_dir()):
        raise ValueError("ruta invalida")
    
    result = {
        "success": False,
        "backup_path": None,
        "removed": {},
        "errors": [],
    }
    
    # Create backup first
    if create_backup:
        backup = _create_self_backup(backup_dir)
        if backup:
            result["backup_path"] = backup
        else:
            result["errors"].append("Failed to create backup")
    
    # Purge each category
    categories = {
        "logs": lambda: purge_all_logs(secure),
        "recent_links": lambda: purge_own_recent_links(secure),
        "prefetch": lambda: purge_prefetch(secure),
        "temp_files": lambda: purge_temp_files(secure),
        "registry": lambda: purge_registry_traces(),
    }
    
    for cat, func in categories.items():
        try:
            count = func()
            result["removed"][cat] = count
        except Exception as e:
            result["errors"].append(f"{cat}: {str(e)}")
            result["removed"][cat] = 0
    
    # Finally, remove the base directory itself
    try:
        if secure:
            # Secure delete all files in base dir
            for root, dirs, files in os.walk(target, topdown=False):
                for f in files:
                    secure_delete(os.path.join(root, f))
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except Exception:
                        pass
            os.rmdir(target)
        else:
            shutil.rmtree(target, ignore_errors=True)
        
        result["success"] = not os.path.exists(target)
    except Exception as e:
        result["errors"].append(f"base_dir: {str(e)}")
        result["success"] = False
    
    return result


def list_self_backups(backup_dir: Optional[str] = None) -> List[Dict]:
    """List available self-clean backups."""
    if backup_dir is None:
        backup_dir = tempfile.gettempdir()
    
    backups = []
    try:
        for fname in os.listdir(backup_dir):
            if fname.startswith("duai_self_backup_") and os.path.isdir(os.path.join(backup_dir, fname)):
                fpath = os.path.join(backup_dir, fname)
                manifest_path = os.path.join(fpath, "manifest.json")
                if os.path.exists(manifest_path):
                    import json
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                    backups.append({
                        "path": fpath,
                        "timestamp": manifest.get("timestamp", 0),
                        "version": manifest.get("version", "unknown"),
                        "items": manifest.get("items", []),
                        "source": manifest.get("source", ""),
                    })
    except Exception:
        pass
    
    return sorted(backups, key=lambda x: x["timestamp"], reverse=True)


def verify_clean(verify_base: Optional[str] = None) -> Dict[str, Any]:
    """Verify that self-clean was thorough."""
    target = verify_base or base_dir()
    result = {
        "clean": True,
        "remaining": [],
        "errors": [],
    }
    
    if os.path.exists(target):
        result["clean"] = False
        for root, dirs, files in os.walk(target):
            for f in files:
                result["remaining"].append(os.path.join(root, f))
            for d in dirs:
                result["remaining"].append(os.path.join(root, d))
    
    # Check common locations
    check_paths = [
        os.path.join(logs_dir(), "duai.log"),
        os.path.join(tempfile.gettempdir(), "duai_*"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Prefetch", "DUAI*.PF"),
    ]
    
    import glob
    for pattern in check_paths:
        for f in glob.glob(pattern):
            if os.path.exists(f):
                result["clean"] = False
                result["remaining"].append(f)
    
    return result