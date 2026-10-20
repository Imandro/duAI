"""System cleaning utilities with extended features and safety."""

import os
import subprocess
import time
from typing import Any, Dict, List, Tuple, Optional
from ..utils.paths import delete_filesystem, expand, iter_paths, path_size
from ..utils.logger import log
from ..utils.settings import get_settings


def clean_temp_files(exclude: List[str] = None) -> Tuple[int, int]:
    """Clean temporary files with exclusion list."""
    if exclude is None:
        exclude = ["duAI", "du-ai", "duai"]
    
    temp_root = expand("%LOCALAPPDATA%/Temp")
    freed = 0
    removed = 0
    
    if not os.path.isdir(temp_root):
        return 0, 0
    
    for name in os.listdir(temp_root):
        if any(ex.lower() in name.lower() for ex in exclude):
            continue
        full = os.path.join(temp_root, name)
        try:
            size = path_size(full)
            if delete_filesystem(full, permanent=True):
                freed += size
                removed += 1
        except Exception:
            pass
    
    return removed, freed


def clean_recent_items() -> int:
    """Clean recent items (jump lists, recent files)."""
    recent = expand("%APPDATA%/Microsoft/Windows/Recent")
    count = 0
    
    for sub in ("AutomaticDestinations", "CustomDestinations"):
        folder = os.path.join(recent, sub)
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                try:
                    if delete_filesystem(os.path.join(folder, name), permanent=True):
                        count += 1
                except Exception:
                    pass
    
    if os.path.isdir(recent):
        for pattern in ("*.lnk", "*.txt"):
            for item in iter_paths(os.path.join(recent, pattern)):
                try:
                    if delete_filesystem(item, permanent=True):
                        count += 1
                except Exception:
                    pass
    
    return count


def clean_prefetch(ai_only: bool = True) -> int:
    """Clean prefetch files, optionally AI-only."""
    from .targets import AI_MARKERS as MARKERS
    
    prefetch_dir = r"C:\Windows\Prefetch"
    count = 0
    
    try:
        names = os.listdir(prefetch_dir)
    except OSError:
        return 0
    
    for name in names:
        lowered = name.lower()
        if not lowered.endswith(".pf"):
            continue
        
        if ai_only:
            if not any(marker in lowered for marker in MARKERS):
                continue
        
        try:
            if delete_filesystem(os.path.join(prefetch_dir, name), permanent=True):
                count += 1
        except Exception:
            pass
    
    return count


def flush_dns() -> bool:
    """Flush DNS cache."""
    try:
        result = subprocess.run(
            ["ipconfig", "/flushdns"], 
            capture_output=True, text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception:
        return False


def clear_clipboard() -> bool:
    """Clear clipboard and history."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        
        if not user32.OpenClipboard(None):
            return False
        
        try:
            user32.EmptyClipboard()
            deleted_history = False
            if hasattr(user32, "DeleteClipboardHistory"):
                deleted_history = bool(user32.DeleteClipboardHistory(None))
            return deleted_history or True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def clean_timeline() -> bool:
    """Clean Windows Timeline (activity history)."""
    db = expand("%LOCALAPPDATA%/Microsoft/Windows/Apps/activitiesCache.db")
    
    if not os.path.exists(db):
        return True
    
    # Remove WAL and SHM files first
    for suffix in ("-wal", "-shm"):
        extra = db + suffix
        if os.path.exists(extra):
            try:
                os.remove(extra)
            except OSError:
                pass
    
    try:
        os.remove(db)
        return True
    except OSError:
        return False


def clean_location_history() -> int:
    """Clean location history data."""
    dirs = [
        expand("%PROGRAMDATA%/Microsoft/Windows/LocationData"),
        expand("%LOCALAPPDATA%/Microsoft/Windows/LocationHistory"),
    ]
    removed = 0
    
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        
        for root, _dirs, files in os.walk(root_dir):
            for name in files:
                try:
                    if delete_filesystem(os.path.join(root, name), permanent=True):
                        removed += 1
                except Exception:
                    pass
    
    return removed


def clean_windows_update_cleanup() -> Tuple[int, int]:
    """Clean Windows Update cleanup files (requires admin)."""
    freed = 0
    removed = 0
    
    paths = [
        r"C:\Windows\SoftwareDistribution\Download",
        r"C:\Windows\Logs\CBS",
        r"C:\Windows\Temp",
    ]
    
    for path in paths:
        if not os.path.isdir(path):
            continue
        
        for root, dirs, files in os.walk(path):
            for name in files:
                full = os.path.join(root, name)
                try:
                    size = path_size(full)
                    if delete_filesystem(full, permanent=True):
                        freed += size
                        removed += 1
                except Exception:
                    pass
    
    return removed, freed


def clean_delivery_optimization() -> Tuple[int, int]:
    """Clean Delivery Optimization files (Windows Update P2P)."""
    freed = 0
    removed = 0
    
    path = r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization"
    
    if not os.path.isdir(path):
        return 0, 0
    
    for root, dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                size = path_size(full)
                if delete_filesystem(full, permanent=True):
                    freed += size
                    removed += 1
            except Exception:
                pass
    
    return removed, freed


def clean_memory_dumps() -> Tuple[int, int]:
    """Clean memory dump files."""
    freed = 0
    removed = 0
    
    paths = [
        r"C:\Windows\MEMORY.DMP",
        r"C:\Windows\Minidump",
    ]
    
    for path in paths:
        if os.path.isfile(path):
            try:
                size = path_size(path)
                if delete_filesystem(path, permanent=True):
                    freed += size
                    removed += 1
            except Exception:
                pass
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for name in files:
                    full = os.path.join(root, name)
                    try:
                        size = path_size(full)
                        if delete_filesystem(full, permanent=True):
                            freed += size
                            removed += 1
                    except Exception:
                        pass
    
    return removed, freed


def clean_thumbnails() -> Tuple[int, int]:
    """Clean thumbnail cache."""
    freed = 0
    removed = 0
    
    paths = [
        expand("%LOCALAPPDATA%/Microsoft/Windows/Explorer/thumbcache_*.db"),
        expand("%LOCALAPPDATA%/Microsoft/Windows/Explorer/iconcache_*.db"),
    ]
    
    import glob
    for pattern in paths:
        for full in glob.glob(pattern):
            try:
                size = path_size(full)
                if delete_filesystem(full, permanent=True):
                    freed += size
                    removed += 1
            except Exception:
                pass
    
    return removed, freed


def clean_font_cache() -> Tuple[int, int]:
    """Clean font cache."""
    freed = 0
    removed = 0
    
    path = r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"
    
    if not os.path.isdir(path):
        return 0, 0
    
    for root, dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                size = path_size(full)
                if delete_filesystem(full, permanent=True):
                    freed += size
                    removed += 1
            except Exception:
                pass
    
    return removed, freed


def clean_old_chkdsk() -> Tuple[int, int]:
    """Clean old CHKDSK log files."""
    freed = 0
    removed = 0
    
    path = r"C:\Windows\Logs\CBS"
    
    if not os.path.isdir(path):
        return 0, 0
    
    for root, dirs, files in os.walk(path):
        for name in files:
            if name.lower().startswith("chkdsk") and name.lower().endswith(".log"):
                full = os.path.join(root, name)
                try:
                    size = path_size(full)
                    if delete_filesystem(full, permanent=True):
                        freed += size
                        removed += 1
                except Exception:
                    pass
    
    return removed, freed


def clean_event_logs() -> int:
    """Clear Windows Event Logs (requires admin)."""
    try:
        result = subprocess.run(
            ["wevtutil", "cl", "System"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            subprocess.run(
                ["wevtutil", "cl", "Application"],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
    except Exception:
        pass
    return False


# Hosts file blocking
HOSTS_BLOCK_START = "# === duAI BLOCK START ==="
HOSTS_BLOCK_END = "# === duAI BLOCK END ==="
HOSTS_DOMAINS = [
    "telemetry.openai.com",
    "o33249.ingest.sentry-cdn.com",
    "api.statsig.com",
    "featuregates.org",
    "statsig.anthropic.com",
    "events.statsigapi.net",
    "telemetry.microsoft.com",
    "vortex.data.microsoft.com",
    "settings-win.data.microsoft.com",
]


def hosts_file_path() -> str:
    """Get hosts file path."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")


def set_hosts_block(enable: bool) -> int:
    """Enable or disable hosts file blocking."""
    path = hosts_file_path()
    
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError as exc:
        raise PermissionError(str(exc))
    
    cleaned = []
    inside_block = False
    
    for line in lines:
        stripped = line.strip()
        if stripped == HOSTS_BLOCK_START:
            inside_block = True
            continue
        if stripped == HOSTS_BLOCK_END:
            inside_block = False
            continue
        if not inside_block:
            cleaned.append(line.rstrip("\n"))
    
    if enable:
        cleaned.append(HOSTS_BLOCK_START)
        for domain in HOSTS_DOMAINS:
            cleaned.append(f"0.0.0.0 {domain}")
        cleaned.append(HOSTS_BLOCK_END)
    
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(cleaned) + "\n")
    except OSError as exc:
        raise PermissionError(str(exc))
    
    return len(HOSTS_DOMAINS) if enable else 0


def hosts_block_active() -> bool:
    """Check if hosts blocking is active."""
    try:
        with open(hosts_file_path(), "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        return HOSTS_BLOCK_START in content
    except OSError:
        return False


def get_blocked_domains() -> List[str]:
    """Get list of currently blocked domains."""
    return HOSTS_DOMAINS.copy()


def add_blocked_domain(domain: str) -> bool:
    """Add a domain to the block list."""
    global HOSTS_DOMAINS
    if domain not in HOSTS_DOMAINS:
        HOSTS_DOMAINS.append(domain)
        return set_hosts_block(hosts_block_active()) > 0
    return False


def remove_blocked_domain(domain: str) -> bool:
    """Remove a domain from the block list."""
    global HOSTS_DOMAINS
    if domain in HOSTS_DOMAINS:
        HOSTS_DOMAINS.remove(domain)
        return set_hosts_block(hosts_block_active()) > 0
    return False


# System maintenance
def run_dism_cleanup() -> bool:
    """Run DISM cleanup (requires admin)."""
    try:
        result = subprocess.run(
            ["dism", "/online", "/cleanup-image", "/startcomponentcleanup"],
            capture_output=True, text=True, timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception:
        return False


def run_sfc_scan() -> bool:
    """Run System File Checker (requires admin)."""
    try:
        result = subprocess.run(
            ["sfc", "/scannow"],
            capture_output=True, text=True, timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception:
        return False


def optimize_drives() -> bool:
    """Run drive optimization (trim/defrag)."""
    try:
        result = subprocess.run(
            ["defrag", "C:", "/O"],
            capture_output=True, text=True, timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception:
        return False


# Master clean function
def run_system_clean(
    temp: bool = True,
    recent: bool = True,
    prefetch: bool = True,
    dns: bool = True,
    clipboard: bool = True,
    timeline: bool = True,
    location: bool = True,
    thumbnails: bool = True,
    font_cache: bool = True,
    hosts_block: bool = False,
    windows_update: bool = False,
    delivery_opt: bool = False,
    memory_dumps: bool = False,
    chkdsk_logs: bool = False,
    event_logs: bool = False,
    dism: bool = False,
    sfc: bool = False,
    optimize: bool = False,
    ai_only_prefetch: bool = True,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """Run comprehensive system clean."""
    
    results = {
        "categories": {},
        "total_removed": 0,
        "total_freed": 0,
        "errors": [],
        "duration": 0,
    }
    
    start_time = time.time()
    
    # Define clean operations
    operations = [
        ("temp", temp, lambda: clean_temp_files()),
        ("recent", recent, clean_recent_items),
        ("prefetch", prefetch, lambda: clean_prefetch(ai_only_prefetch)),
        ("dns", dns, flush_dns),
        ("clipboard", clipboard, clear_clipboard),
        ("timeline", timeline, clean_timeline),
        ("location", location, clean_location_history),
        ("thumbnails", thumbnails, clean_thumbnails),
        ("font_cache", font_cache, clean_font_cache),
        ("windows_update", windows_update, clean_windows_update_cleanup),
        ("delivery_opt", delivery_opt, clean_delivery_optimization),
        ("memory_dumps", memory_dumps, clean_memory_dumps),
        ("chkdsk_logs", chkdsk_logs, clean_old_chkdsk),
        ("event_logs", event_logs, clean_event_logs),
        ("dism", dism, run_dism_cleanup),
        ("sfc", sfc, run_sfc_scan),
        ("optimize", optimize, optimize_drives),
    ]
    
    for name, enabled, func in operations:
        if not enabled:
            continue
        
        if progress_callback:
            progress_callback({"stage": name, "status": "running"})
        
        try:
            if name in ["windows_update", "delivery_opt", "memory_dumps", 
                        "chkdsk_logs", "thumbnails", "font_cache"]:
                removed, freed = func()
                results["categories"][name] = {"removed": removed, "freed_bytes": freed}
                results["total_removed"] += removed
                results["total_freed"] += freed
            else:
                result = func()
                if isinstance(result, tuple):
                    removed, freed = result
                    results["categories"][name] = {"removed": removed, "freed_bytes": freed}
                    results["total_removed"] += removed
                    results["total_freed"] += freed
                else:
                    results["categories"][name] = {"success": bool(result)}
        except Exception as e:
            results["errors"].append(f"{name}: {str(e)}")
            log("system_clean", category=name, error=str(e))
        
        if progress_callback:
            progress_callback({"stage": name, "status": "completed"})
    
    # Hosts block
    if hosts_block:
        try:
            count = set_hosts_block(True)
            results["categories"]["hosts_block"] = {"blocked_domains": count}
        except Exception as e:
            results["errors"].append(f"hosts_block: {str(e)}")
    
    results["duration"] = time.time() - start_time
    log("system_clean", **results)
    
    return results