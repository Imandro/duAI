"""Registry cleaning with backup, dry-run, and AI-filtered deletion."""

import codecs
import json
import os
import tempfile
import time
import winreg
from typing import Dict, List, Optional, Any
from .targets import AI_MARKERS as MARKERS


_EXPLORER_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Explorer"

KEYS_AI_FILTERED = {
    "UserAssist": _EXPLORER_ROOT + r"\UserAssist",
    "MuiCache": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
}

KEYS_GENERAL = {
    "RunMRU": _EXPLORER_ROOT + r"\RunMRU",
    "TypedPaths": _EXPLORER_ROOT + r"\TypedPaths",
    "RecentDocs": _EXPLORER_ROOT + r"\RecentDocs",
    "OpenSavePidlMRU": _EXPLORER_ROOT + r"\ComDlg32\OpenSavePidlMRU",
    "LastVisitedPidlMRU": _EXPLORER_ROOT + r"\ComDlg32\LastVisitedPidlMRU",
}

# Additional AI-specific registry keys
KEYS_AI_SPECIFIC = {
    "AI_RunMRU": r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
    "AI_AppPaths": r"Software\Microsoft\Windows\CurrentVersion\App Paths",
    "AI_TypedURLs": r"Software\Microsoft\Internet Explorer\TypedURLs",
    "AI_WordWheel": r"Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery",
    "AI_RecentDocs": _EXPLORER_ROOT + r"\RecentDocs",
    "AI_Cortana": r"Software\Microsoft\Windows\CurrentVersion\Search",
    "AI_StartMenu": r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartPage",
}


def rot13(text: str) -> str:
    return codecs.encode(text, "rot_13")


def _matches_ai(name: str) -> bool:
    """Check if a registry value name matches AI markers."""
    lowered = name.lower()
    return any(marker in lowered for marker in MARKERS)


def _collect_key_values(hkey: int, path: str) -> List[Dict[str, Any]]:
    """Collect all values from a registry key for backup."""
    values = []
    try:
        with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
            value_index = 0
            while True:
                try:
                    value_name, value_data, value_type = winreg.EnumValue(key, value_index)
                    values.append({
                        "name": value_name,
                        "data": value_data,
                        "type": value_type,
                    })
                    value_index += 1
                except OSError:
                    break
    except OSError:
        pass
    return values


def _collect_key_subkeys(hkey: int, path: str) -> List[Dict[str, Any]]:
    """Collect all subkeys from a registry key for backup."""
    subkeys = []
    try:
        with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
            sub_index = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(key, sub_index)
                    subkeys.append({
                        "name": sub_name,
                        "values": _collect_key_values(hkey, f"{path}\\{sub_name}"),
                        "subkeys": _collect_key_subkeys(hkey, f"{path}\\{sub_name}"),
                    })
                    sub_index += 1
                except OSError:
                    break
    except OSError:
        pass
    return subkeys


def _create_backup(hkey: int, paths: Dict[str, str], backup_path: str) -> bool:
    """Create a full backup of registry keys to JSON file."""
    backup_data = {
        "timestamp": time.time(),
        "keys": {},
    }
    
    for label, path in paths.items():
        backup_data["keys"][label] = {
            "path": path,
            "values": _collect_key_values(hkey, path),
            "subkeys": _collect_key_subkeys(hkey, path),
        }
    
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, default=str)
        return True
    except Exception:
        return False


def _restore_backup(hkey: int, backup_path: str) -> bool:
    """Restore registry from backup file."""
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
    except Exception:
        return False
    
    for label, key_data in backup_data.get("keys", {}).items():
        path = key_data["path"]
        try:
            # Create key if it doesn't exist
            with winreg.CreateKey(hkey, path) as key:
                pass
            
            # Restore values
            for val in key_data.get("values", []):
                try:
                    with winreg.OpenKey(hkey, path, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.SetValueEx(key, val["name"], 0, val["type"], val["data"])
                except Exception:
                    pass
            
            # Restore subkeys recursively
            def restore_subkeys(parent_path: str, subkeys: List[Dict]):
                for sk in subkeys:
                    sub_path = f"{parent_path}\\{sk['name']}"
                    try:
                        with winreg.CreateKey(hkey, sub_path) as key:
                            pass
                        for val in sk.get("values", []):
                            try:
                                with winreg.OpenKey(hkey, sub_path, 0, winreg.KEY_SET_VALUE) as key:
                                    winreg.SetValueEx(key, val["name"], 0, val["type"], val["data"])
                            except Exception:
                                pass
                        restore_subkeys(sub_path, sk.get("subkeys", []))
                    except Exception:
                        pass
            
            restore_subkeys(path, key_data.get("subkeys", []))
        except Exception:
            pass
    
    return True


def collect_registry_traces(ai_only: bool = True) -> Dict[str, int]:
    """Collect registry trace counts. If ai_only=True, only count AI-related entries."""
    counts = {}
    
    for label, path in KEYS_AI_FILTERED.items():
        count = 0
        try:
            if label == "UserAssist":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as root:
                    index = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root, sub_name + r"\Count") as count_key:
                                value_index = 0
                                while True:
                                    try:
                                        value_name, _, _ = winreg.EnumValue(count_key, value_index)
                                    except OSError:
                                        break
                                    value_index += 1
                                    decoded = rot13(value_name)
                                    if not ai_only or _matches_ai(decoded):
                                        count += 1
                        except OSError:
                            continue
            else:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                    value_index = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        if not ai_only or _matches_ai(value_name):
                            count += 1
        except OSError:
            pass
        counts[label] = count
    
    for label, path in KEYS_GENERAL.items():
        count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                info = winreg.QueryInfoKey(key)
                if ai_only:
                    # Count only AI-related for general keys
                    value_index = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        if _matches_ai(value_name):
                            count += 1
                else:
                    count = info[0] + info[1]
        except OSError:
            pass
        counts[label] = count
    
    # AI-specific keys (always AI-filtered)
    for label, path in KEYS_AI_SPECIFIC.items():
        count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                value_index = 0
                while True:
                    try:
                        value_name, _, _ = winreg.EnumValue(key, value_index)
                    except OSError:
                        break
                    value_index += 1
                    if _matches_ai(value_name):
                        count += 1
        except OSError:
            pass
        counts[label] = count
    
    return counts


def clean_registry(
    ai_only: bool = True,
    dry_run: bool = False,
    create_backup: bool = True,
    backup_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Clean registry traces.
    
    Args:
        ai_only: If True, only remove AI-related entries. If False, clean all.
        dry_run: If True, only simulate and return what would be removed.
        create_backup: If True, create a backup before cleaning.
        backup_path: Custom backup path. If None, uses temp file.
    
    Returns:
        Dict with removed counts, backup path, and dry_run status.
    """
    result = {
        "removed": {},
        "backup_path": None,
        "dry_run": dry_run,
        "errors": [],
    }
    
    # Create backup if requested
    if create_backup and not dry_run:
        if backup_path is None:
            backup_path = os.path.join(tempfile.gettempdir(), f"duai_registry_backup_{int(time.time())}.json")
        
        all_keys = {**KEYS_AI_FILTERED, **KEYS_GENERAL, **KEYS_AI_SPECIFIC}
        if _create_backup(winreg.HKEY_CURRENT_USER, all_keys, backup_path):
            result["backup_path"] = backup_path
        else:
            result["errors"].append("Failed to create registry backup")
            if not dry_run:
                # Don't proceed without backup
                return result
    
    all_keys = {**KEYS_AI_FILTERED, **KEYS_GENERAL, **KEYS_AI_SPECIFIC}
    
    for label, path in all_keys.items():
        count = 0
        is_ai_filtered = label in KEYS_AI_FILTERED or label in KEYS_AI_SPECIFIC
        
        try:
            if label == "UserAssist":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as root:
                    index = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root, sub_name + r"\Count", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as count_key:
                                names = []
                                value_index = 0
                                while True:
                                    try:
                                        value_name, _, _ = winreg.EnumValue(count_key, value_index)
                                    except OSError:
                                        break
                                    value_index += 1
                                    names.append(value_name)
                                for value_name in names:
                                    decoded = rot13(value_name)
                                    should_remove = (not ai_only) or (is_ai_filtered and _matches_ai(decoded))
                                    if should_remove:
                                        if not dry_run:
                                            try:
                                                winreg.DeleteValue(count_key, value_name)
                                            except OSError:
                                                pass
                                        count += 1
                        except OSError:
                            continue
            elif is_ai_filtered:
                # AI-filtered keys
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                    names = []
                    value_index = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        names.append(value_name)
                    for value_name in names:
                        should_remove = (not ai_only) or _matches_ai(value_name)
                        if should_remove:
                            if not dry_run:
                                try:
                                    winreg.DeleteValue(key, value_name)
                                except OSError:
                                    pass
                            count += 1
            else:
                # General keys - clean all or AI-filtered based on ai_only
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    if label in ("RunMRU", "TypedPaths", "TypedURLs"):
                        info = winreg.QueryInfoKey(key)
                        for value_index in range(info[1] - 1, -1, -1):
                            try:
                                value_name = winreg.EnumValue(key, value_index)[0]
                            except OSError:
                                continue
                            should_remove = (not ai_only) or _matches_ai(value_name)
                            if should_remove:
                                if not dry_run:
                                    try:
                                        winreg.DeleteValue(key, value_name)
                                    except OSError:
                                        pass
                                count += 1
                    else:
                        info = winreg.QueryInfoKey(key)
                        for sub_index in range(info[0] - 1, -1, -1):
                            try:
                                sub_name = winreg.EnumKey(key, sub_index)
                            except OSError:
                                continue
                            should_remove = (not ai_only) or _matches_ai(sub_name)
                            if should_remove:
                                if not dry_run:
                                    try:
                                        winreg.DeleteKey(key, sub_name)
                                    except OSError:
                                        pass
                                count += 1
        except OSError as e:
            result["errors"].append(f"{label}: {str(e)}")
        except Exception as e:
            result["errors"].append(f"{label}: {str(e)}")
        
        result["removed"][label] = count
    
    return result


def restore_registry_backup(backup_path: str) -> Dict[str, Any]:
    """Restore registry from a backup file."""
    result = {"success": False, "errors": []}
    if _restore_backup(winreg.HKEY_CURRENT_USER, backup_path):
        result["success"] = True
    else:
        result["errors"].append("Failed to restore registry backup")
    return result


def list_backups(backup_dir: Optional[str] = None) -> List[Dict]:
    """List available registry backups."""
    if backup_dir is None:
        backup_dir = tempfile.gettempdir()
    
    backups = []
    try:
        for f in os.listdir(backup_dir):
            if f.startswith("duai_registry_backup_") and f.endswith(".json"):
                path = os.path.join(backup_dir, f)
                stat = os.stat(path)
                try:
                    with open(path, "r") as fp:
                        data = json.load(fp)
                    backups.append({
                        "path": path,
                        "timestamp": data.get("timestamp", stat.st_mtime),
                        "keys_count": len(data.get("keys", {})),
                        "size": stat.st_size,
                    })
                except Exception:
                    pass
    except Exception:
        pass
    
    return sorted(backups, key=lambda x: x["timestamp"], reverse=True)