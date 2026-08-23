import os
import re
import sqlite3
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import registry_clean
from ..utils.paths import expand, iter_paths, path_size, running_conflicts, is_admin

STATUS_FOUND = "found"
STATUS_EMPTY = "empty"
STATUS_LOCKED = "locked"
STATUS_ADMIN = "admin"
STATUS_READY = "ready"
STATUS_ERROR = "error"

_STATUS_LABEL = {
    STATUS_FOUND: "RASTRO DETECTADO",
    STATUS_EMPTY: "LIMPIO",
    STATUS_LOCKED: "BLOQUEADO",
    STATUS_ADMIN: "REQUIERE ADMIN",
    STATUS_READY: "DISPONIBLE",
    STATUS_ERROR: "ERROR",
}


class TraceItem:
    __slots__ = ("path", "size")

    def __init__(self, path, size=0):
        self.path = path
        self.size = size


class ScanEntry:
    def __init__(self, target):
        self.target = target
        self.status = STATUS_EMPTY
        self.items = []
        self.detail = ""

    @property
    def status_label(self):
        return _STATUS_LABEL.get(self.status, self.status)

    @property
    def total_bytes(self):
        return sum(item.size for item in self.items)


class ScanReport:
    def __init__(self):
        self.entries = []
        self.scanned_at = ""

    @property
    def found_entries(self):
        return [e for e in self.entries if e.status == STATUS_FOUND]

    @property
    def total_bytes(self):
        return sum(e.total_bytes for e in self.entries)

    def entry_by_id(self, target_id):
        for entry in self.entries:
            if entry.target.id == target_id:
                return entry
        return None


def scan_targets(targets):
    return scan_targets_parallel(targets, progress_cb=None)


def scan_targets_parallel(targets, progress_cb=None):
    report = ScanReport()
    report.scanned_at = time.strftime("%Y-%m-%d %H:%M:%S")
    total = len(targets)

    def _scan_one(target):
        entry = ScanEntry(target)
        try:
            if target.kind_action == "registry":
                counts = registry_clean.collect_registry_traces()
                t = sum(counts.values())
                entry.status = STATUS_FOUND if t else STATUS_EMPTY
                entry.detail = ", ".join(f"{k}: {v}" for k, v in counts.items() if v)
                if t:
                    entry.items.append(TraceItem("Registro de Windows", 0))

            elif target.kind_action == "dns":
                entry = _scan_dns(target)

            elif target.kind_action == "clipboard":
                entry = _scan_clipboard(target)

            elif target.kind_action in ("timeline", "location"):
                items = _action_paths(target)
                if items:
                    entry.status = STATUS_FOUND
                    entry.items = [
                        TraceItem(p, path_size(p)) for p in items if os.path.exists(p)
                    ]
                    if not entry.items:
                        entry.status = STATUS_EMPTY
                else:
                    entry.status = STATUS_EMPTY

            elif target.kind in ("browser_history", "browser_storage"):
                if running_conflicts(target.processes):
                    entry.status = STATUS_LOCKED
                    entry.detail = "Cierra " + ", ".join(running_conflicts(target.processes))
                else:
                    if target.kind == "browser_history":
                        entry = _scan_browser_history(target)
                    else:
                        entry.items = [TraceItem(p, path_size(p)) for p in _resolve_browser(target)]
                        entry.status = STATUS_FOUND if entry.items else STATUS_EMPTY
            else:
                if running_conflicts(target.processes):
                    entry.status = STATUS_LOCKED
                    entry.detail = "Cierra " + ", ".join(running_conflicts(target.processes))
                elif target.requires_admin and not is_admin():
                    entry.status = STATUS_ADMIN
                else:
                    paths = []
                    for pattern in target.paths:
                        paths.extend(iter_paths(pattern))
                    seen = set()
                    unique = []
                    for p in paths:
                        low = os.path.normcase(os.path.abspath(p))
                        if low not in seen:
                            seen.add(low)
                            unique.append(p)
                    if target.filter_markers:
                        from .targets import AI_MARKERS
                        filtered = []
                        for p in unique:
                            name = os.path.basename(p).lower()
                            if any(marker in name for marker in AI_MARKERS):
                                filtered.append(p)
                        unique = filtered
                    if target.id == "temp_files":
                        unique = [
                            p for p in unique
                            if os.path.basename(p) != "duAI" and expand("%LOCALAPPDATA%/Temp") != p
                        ]
                    entry.items = [TraceItem(p, path_size(p)) for p in unique]
                    entry.status = STATUS_FOUND if entry.items else STATUS_EMPTY
        except Exception as exc:
            entry.status = STATUS_ERROR
            entry.detail = str(exc)
        return entry

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_scan_one, t): t for t in targets}
        for i, future in enumerate(as_completed(futures), 1):
            entry = future.result()
            report.entries.append(entry)
            if progress_cb:
                progress_cb(i, total, entry.target.name)

    report.entries.sort(key=lambda e: targets.index(e.target) if e.target in targets else 999)
    return report


def _scan_dns(target):
    entry = ScanEntry(target)
    try:
        result = subprocess.run(
            ["ipconfig", "/displaydns"],
            capture_output=True, text=True, timeout=15, creationflags=0x08000000
        )
        output = result.stdout.lower()
        domains = (target.meta or {}).get("domains", [])
        if not domains:
            from .targets import load_catalog
            domains = [d.lower() for d in load_catalog().get("domains", [])]
        found_domains = [d for d in domains if d in output]
        if found_domains:
            entry.status = STATUS_FOUND
            entry.detail = ", ".join(found_domains)
            entry.items = [TraceItem(f"DNS: {d}", 0) for d in found_domains]
        else:
            entry.status = STATUS_EMPTY
    except Exception as exc:
        entry.status = STATUS_ERROR
        entry.detail = str(exc)
    return entry


def _scan_clipboard(target):
    entry = ScanEntry(target)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        has_history = user32.GetClipboardSequenceNumber() > 0
        entry.status = STATUS_FOUND if has_history else STATUS_EMPTY
        if has_history:
            entry.detail = "Historial del portapapeles activo"
            entry.items = [TraceItem("Portapapeles", 0)]
    except Exception as exc:
        entry.status = STATUS_READY
        entry.detail = str(exc)
    return entry


def _scan_browser_history(target):
    entry = ScanEntry(target)
    meta = target.meta or {}
    base = expand(meta.get("base", ""))
    engine = meta.get("engine", "chromium")
    profile_dirs = meta.get("profile_dirs", ["Default"])
    domains = [d.lower() for d in meta.get("domains", [])]

    if not os.path.isdir(base):
        entry.status = STATUS_EMPTY
        return entry

    total_visits = 0
    matched_paths = []

    for pattern in profile_dirs:
        for profile in iter_paths(os.path.join(base, pattern)):
            if not os.path.isdir(profile):
                continue
            db_name = "places.sqlite" if engine == "firefox" else "History"
            db = os.path.join(profile, db_name)
            if not os.path.isfile(db):
                continue
            try:
                tmp = os.path.join(tempfile.gettempdir(), f"duai_scan_{os.getpid()}.db")
                import shutil
                shutil.copy2(db, tmp)
                conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
                cur = conn.cursor()
                if engine == "firefox":
                    for domain in domains:
                        like = f"%{domain}%"
                        cur.execute(
                            "SELECT COUNT(*) FROM moz_places WHERE url LIKE ? OR title LIKE ?",
                            (like, like)
                        )
                        count = cur.fetchone()[0]
                        if count:
                            total_visits += count
                            matched_paths.append(f"{domain} ({count} visitas)")
                else:
                    for domain in domains:
                        like = f"%{domain}%"
                        cur.execute(
                            "SELECT COUNT(*) FROM urls WHERE url LIKE ? OR title LIKE ?",
                            (like, like)
                        )
                        count = cur.fetchone()[0]
                        if count:
                            total_visits += count
                            matched_paths.append(f"{domain} ({count} visitas)")
                conn.close()
                os.unlink(tmp)
            except Exception:
                pass

            if target.kind == "browser_history" and total_visits == 0:
                entry.items = [TraceItem(p, path_size(p)) for p in _resolve_browser(target)]
                entry.status = STATUS_FOUND if entry.items else STATUS_EMPTY
            else:
                break

        if total_visits > 0:
            break

    if total_visits > 0:
        entry.status = STATUS_FOUND
        entry.detail = f"{total_visits} visitas a sitios de IA"
        entry.items = [TraceItem(m, 0) for m in matched_paths]
    elif not matched_paths:
        entry.status = STATUS_EMPTY

    return entry


def _action_paths(target):
    results = []
    if target.kind_action == "timeline":
        db = expand("%LOCALAPPDATA%/Microsoft/Windows/Apps/activitiesCache.db")
        if os.path.exists(db):
            results.append(db)
    elif target.kind_action == "location":
        data_dirs = [
            expand("%PROGRAMDATA%/Microsoft/Windows/LocationData"),
            expand("%LOCALAPPDATA%/Microsoft/Windows/LocationHistory"),
        ]
        for d in data_dirs:
            if os.path.isdir(d):
                for root, _dirs, files in os.walk(d):
                    for name in files:
                        results.append(os.path.join(root, name))
    return results


def _resolve_browser(target):
    meta = target.meta or {}
    base = expand(meta.get("base", ""))
    engine = meta.get("engine", "chromium")
    profile_dirs = meta.get("profile_dirs", ["Default"])
    results = []
    if not os.path.isdir(base):
        return results
    for pattern in profile_dirs:
        for profile in iter_paths(os.path.join(base, pattern)):
            if not os.path.isdir(profile):
                continue
            if target.kind == "browser_history":
                db_name = "places.sqlite" if engine == "firefox" else "History"
                db = os.path.join(profile, db_name)
                if os.path.isfile(db):
                    results.append(db)
            else:
                if engine == "firefox":
                    candidates = [
                        os.path.join(profile, "webappsstore.sqlite"),
                        os.path.join(profile, "sessionstore-backups"),
                    ]
                else:
                    candidates = [
                        os.path.join(profile, "Local Storage"),
                        os.path.join(profile, "Session Storage"),
                        os.path.join(profile, "Sessions"),
                    ]
                results.extend(c for c in candidates if os.path.exists(c))
    return results
