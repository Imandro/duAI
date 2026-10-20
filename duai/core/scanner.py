"""Escáner de privacidad para duAI - Paralelo, robusto, con progreso detallado."""

import os
import re
import sqlite3
import subprocess
import tempfile
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, Callable, List

from . import registry_clean
from ..utils.paths import expand, iter_paths, path_size, running_conflicts, is_admin
from ..utils.logger import log_debug, log_warning, log_error

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
        self.errors: List[str] = []
        self.scan_duration = 0.0

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


@dataclass
class ScanProgress:
    """Información de progreso detallada con ETA."""
    current: int = 0
    total: int = 0
    current_target: str = ""
    current_target_id: str = ""
    stage: str = "scanning"
    bytes_scanned: int = 0
    files_scanned: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.perf_counter)

    @property
    def percentage(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    @property
    def eta(self) -> Optional[float]:
        if self.current == 0:
            return None
        rate = self.current / self.elapsed
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else None


class ProgressTracker:
    """Tracker de progreso thread-safe con callback throttled."""

    def __init__(self, total: int, callback: Optional[Callable[[ScanProgress], None]] = None, throttle_ms: int = 100):
        self.progress = ScanProgress(total=total)
        self.callback = callback
        self._lock = threading.Lock()
        self._throttle_ms = throttle_ms
        self._last_callback = 0

    def start_target(self, target_id: str, target_name: str):
        with self._lock:
            self.progress.current_target = target_name
            self.progress.current_target_id = target_id
            self.progress.stage = "scanning"
            self._notify()

    def complete_target(self, target_id: str, items_found: int = 0, bytes_found: int = 0, error: bool = False):
        with self._lock:
            self.progress.current += 1
            self.progress.files_scanned += items_found
            self.progress.bytes_scanned += bytes_found
            if error:
                self.progress.errors += 1
            self.progress.stage = "analyzing" if self.progress.current < self.progress.total else "finalizing"
            self._notify()

    def _notify(self):
        if self.callback:
            now = time.perf_counter() * 1000
            if now - self._last_callback >= self._throttle_ms:
                self._last_callback = now
                p = ScanProgress(
                    current=self.progress.current,
                    total=self.progress.total,
                    current_target=self.progress.current_target,
                    current_target_id=self.progress.current_target_id,
                    stage=self.progress.stage,
                    bytes_scanned=self.progress.bytes_scanned,
                    files_scanned=self.progress.files_scanned,
                    errors=self.progress.errors,
                    start_time=self.progress.start_time,
                )
                try:
                    self.callback(p)
                except Exception:
                    log_error("progress_callback_error")


def scan_targets(targets, progress_cb=None):
    return scan_targets_parallel(targets, progress_cb=progress_cb)


def _get_optimal_workers(targets) -> int:
    """Determina workers óptimos según tipo de targets."""
    cpu_count = os.cpu_count() or 4
    io_bound = sum(1 for t in targets if t.kind in ("browser_history", "browser_storage", "dns", "registry", "clipboard", "timeline", "location"))
    file_bound = sum(1 for t in targets if t.kind == "files")
    if io_bound > file_bound:
        return min(cpu_count * 2, 12)
    return min(cpu_count, 8)


def scan_targets_parallel(targets, progress_cb=None, max_workers=None):
    tracker = ProgressTracker(len(targets), progress_cb)
    report = ScanReport()
    report.scanned_at = time.strftime("%Y-%m-%d %H:%M:%S")

    if max_workers is None:
        max_workers = _get_optimal_workers(targets)

    def _scan_one_tracked(target):
        tracker.start_target(target.id, target.name)
        start = time.perf_counter()
        try:
            entry = _scan_one(target)
            entry.scan_duration = time.perf_counter() - start
            tracker.complete_target(target.id, len(entry.items), entry.total_bytes)
            return entry
        except Exception as exc:
            entry = ScanEntry(target)
            entry.status = STATUS_ERROR
            entry.detail = str(exc)
            entry.errors.append(str(exc))
            entry.scan_duration = time.perf_counter() - start
            tracker.complete_target(target.id, error=True)
            log_error("scan_target_failed", target=target.id, error=str(exc))
            return entry

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_one_tracked, t): t for t in targets}
        for future in as_completed(futures):
            entry = future.result()
            report.entries.append(entry)

    # Preservar orden original
    target_order = {t.id: i for i, t in enumerate(targets)}
    report.entries.sort(key=lambda e: target_order.get(e.target.id, 999))

    tracker.progress.stage = "complete"
    if progress_cb:
        progress_cb(tracker.progress)

    return report


# ============================================================
# ESCANEADORES ESPECÍFICOS
# ============================================================

_DNS_CACHE = None
_DNS_CACHE_LOCK = threading.Lock()


def _scan_dns(target):
    entry = ScanEntry(target)
    try:
        global _DNS_CACHE
        with _DNS_CACHE_LOCK:
            if _DNS_CACHE is None:
                result = subprocess.run(
                    ["ipconfig", "/displaydns"],
                    capture_output=True, text=True, timeout=15, creationflags=0x08000000
                )
                _DNS_CACHE = result.stdout.lower()

        domains = (target.meta or {}).get("domains", [])
        if not domains:
            from .targets import load_catalog
            domains = [d.lower() for d in load_catalog().get("domains", [])]

        found_domains = [d for d in domains if d in _DNS_CACHE]
        if found_domains:
            entry.status = STATUS_FOUND
            entry.detail = ", ".join(found_domains)
            entry.items = [TraceItem(f"DNS: {d}", 0) for d in found_domains]
        else:
            entry.status = STATUS_EMPTY
    except subprocess.TimeoutExpired as exc:
        entry.status = STATUS_ERROR
        entry.detail = f"Timeout DNS: {exc}"
        entry.errors.append(str(exc))
    except Exception as exc:
        entry.status = STATUS_ERROR
        entry.detail = str(exc)
        entry.errors.append(str(exc))
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
        entry.errors.append(str(exc))
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

    # Recopilar todos los perfiles primero
    profiles = []
    for pattern in profile_dirs:
        for profile in iter_paths(os.path.join(base, pattern)):
            if os.path.isdir(profile):
                db_name = "places.sqlite" if engine == "firefox" else "History"
                db_path = os.path.join(profile, db_name)
                if os.path.isfile(db_path):
                    profiles.append((profile, db_path))

    total_profiles = len(profiles)
    if total_profiles == 0:
        entry.status = STATUS_EMPTY
        return entry

    for i, (profile, db_path) in enumerate(profiles):
        try:
            tmp = os.path.join(tempfile.gettempdir(), f"duai_scan_{os.getpid()}_{threading.get_ident()}.db")
            import shutil
            shutil.copy2(db_path, tmp)

            conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            conn.execute("PRAGMA query_only = TRUE")
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
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                entry.status = STATUS_LOCKED
                entry.detail = "Base de datos bloqueada"
            else:
                entry.errors.append(f"SQLite: {exc}")
        except Exception as exc:
            entry.errors.append(str(exc))
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

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


def _scan_one(target) -> ScanEntry:
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
            return _scan_dns(target)

        elif target.kind_action == "clipboard":
            return _scan_clipboard(target)

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
                    return _scan_browser_history(target)
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
                    from .targets import matches_ai_marker, scan_file_content_for_ai
                    filtered = []
                    for p in unique:
                        name = os.path.basename(p)
                        if matches_ai_marker(name) or scan_file_content_for_ai(p):
                            filtered.append(p)
                    unique = filtered

                if target.id == "temp_files":
                    unique = [
                        p for p in unique
                        if os.path.basename(p) != "duAI" and expand("%LOCALAPPDATA%/Temp") != p
                    ]

                entry.items = [TraceItem(p, path_size(p)) for p in unique]
                entry.status = STATUS_FOUND if entry.items else STATUS_EMPTY

    except PermissionError as exc:
        entry.status = STATUS_ERROR
        entry.detail = f"Permisos insuficientes: {exc}"
        entry.errors.append(str(exc))
        log_warning("scan_permission_denied", target=target.id, error=str(exc))
    except FileNotFoundError as exc:
        entry.status = STATUS_EMPTY
        entry.detail = f"Ruta no encontrada: {exc}"
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            entry.status = STATUS_LOCKED
            entry.detail = "Base de datos bloqueada"
        else:
            entry.status = STATUS_ERROR
            entry.detail = f"Error base de datos: {exc}"
        entry.errors.append(str(exc))
    except subprocess.TimeoutExpired as exc:
        entry.status = STATUS_ERROR
        entry.detail = f"Timeout: {exc}"
        entry.errors.append(str(exc))
    except MemoryError as exc:
        entry.status = STATUS_ERROR
        entry.detail = "Memoria insuficiente"
        entry.errors.append(str(exc))
        log_error("scan_memory_error", target=target.id)
    except Exception as exc:
        entry.status = STATUS_ERROR
        entry.detail = f"Error: {type(exc).__name__}: {exc}"
        entry.errors.append(str(exc))
        log_error("scan_unexpected_error", target=target.id, error=str(exc))

    return entry