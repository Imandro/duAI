import os
import subprocess

from ..utils.paths import delete_filesystem, expand, iter_paths


def clean_temp_files():
    temp_root = expand("%LOCALAPPDATA%/Temp")
    freed = 0
    removed = 0
    if not os.path.isdir(temp_root):
        return 0, 0
    from ..utils.paths import path_size

    for name in os.listdir(temp_root):
        if name == "duAI":
            continue
        full = os.path.join(temp_root, name)
        size = path_size(full)
        if delete_filesystem(full, permanent=True):
            freed += size
            removed += 1
    return removed, freed


def clean_recent_items():
    recent = expand("%APPDATA%/Microsoft/Windows/Recent")
    count = 0
    for sub in ("AutomaticDestinations", "CustomDestinations"):
        folder = os.path.join(recent, sub)
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if delete_filesystem(os.path.join(folder, name), permanent=True):
                    count += 1
    if os.path.isdir(recent):
        for pattern in ("*.lnk", "*.txt"):
            for item in iter_paths(os.path.join(recent, pattern)):
                if delete_filesystem(item, permanent=True):
                    count += 1
    return count


def clean_prefetch():
    prefetch_dir = r"C:\Windows\Prefetch"
    from .registry_clean import MARKERS

    count = 0
    try:
        names = os.listdir(prefetch_dir)
    except OSError:
        return 0
    for name in names:
        lowered = name.lower()
        if not lowered.endswith(".pf"):
            continue
        if any(marker in lowered for marker in MARKERS):
            if delete_filesystem(os.path.join(prefetch_dir, name), permanent=True):
                count += 1
    return count


def flush_dns():
    result = subprocess.run(
        ["ipconfig", "/flushdns"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
    )
    return result.returncode == 0


def clear_clipboard():
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


def clean_timeline():
    db = expand("%LOCALAPPDATA%/Microsoft/Windows/Apps/activitiesCache.db")
    if not os.path.exists(db):
        return True
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


def clean_location_history():
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
                if delete_filesystem(os.path.join(root, name), permanent=True):
                    removed += 1
    return removed


HOSTS_BLOCK_START = "# === duAI BLOCK START ==="
HOSTS_BLOCK_END = "# === duAI BLOCK END ==="
HOSTS_DOMAINS = [
    "telemetry.openai.com",
    "o33249.ingest.sentry-cdn.com",
    "api.statsig.com",
    "featuregates.org",
    "statsig.anthropic.com",
    "events.statsigapi.net",
]


def hosts_file_path():
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")


def set_hosts_block(enable):
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


def hosts_block_active():
    try:
        with open(hosts_file_path(), "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        return HOSTS_BLOCK_START in content
    except OSError:
        return False
