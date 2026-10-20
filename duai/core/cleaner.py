"""Cleaner module for duAI - Parallel, safe, with verification and undo."""

import os
import shutil
import sqlite3
import tempfile
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict

from . import registry_clean, system_clean
from .scanner import STATUS_FOUND, STATUS_READY, ScanReport
from ..utils.paths import delete_filesystem, fmt_bytes
from .quarantine import quarantine_path


class CleanErrorType(Enum):
    PERMISSION_DENIED = "permission_denied"
    FILE_IN_USE = "file_in_use"
    PATH_NOT_FOUND = "path_not_found"
    DISK_FULL = "disk_full"
    INTEGRITY_ERROR = "integrity_error"
    UNKNOWN = "unknown"


@dataclass
class CleanError:
    path: str
    error_type: CleanErrorType
    message: str
    recoverable: bool
    retry_count: int = 0


class CleanOptions:
    MODE_RECYCLE = "recycle"
    MODE_PERMANENT = "permanent"
    MODE_QUARANTINE = "quarantine"

    def __init__(
        self,
        selected=None,
        permanent=False,
        preview=False,
        mode=None,
        require_confirmation=True,
        max_file_size=None,
        protected_paths=None,
        verify_before_delete=True,
    ):
        self.selected = selected or set()
        self.preview = preview
        if mode in (self.MODE_RECYCLE, self.MODE_PERMANENT, self.MODE_QUARANTINE):
            self.mode = mode
        else:
            self.mode = self.MODE_PERMANENT if permanent else self.MODE_RECYCLE

        self.require_confirmation = require_confirmation
        self.max_file_size = max_file_size
        self.protected_paths = protected_paths or set()
        self.verify_before_delete = verify_before_delete

    @property
    def permanent(self):
        return self.mode == self.MODE_PERMANENT


class CleanResult:
    def __init__(self):
        self.lines = []
        self.freed_bytes = 0
        self.removed_items = 0
        self.errors = 0
        self.preview = False
        self.quarantine_tokens: List[str] = []
        self.undo_data: List[Dict] = []
        self.detailed_errors: List[CleanError] = []
        self.before_space: Dict[str, int] = {}
        self.after_space: Dict[str, int] = {}
        self.space_by_drive: Dict[str, Dict] = {}

    def add(self, line):
        self.lines.append(line)

    def summary(self) -> str:
        """Resumen legible del resultado de la limpieza."""
        from ..utils.paths import fmt_bytes

        if self.preview:
            head = "SIMULACION (no se elimino nada)"
        else:
            head = "LIMPIEZA COMPLETADA"

        lines = [
            head,
            "=" * 30,
            f"Elementos eliminados: {self.removed_items}",
            f"Espacio liberado: {fmt_bytes(self.freed_bytes)}",
        ]

        if self.quarantine_tokens:
            lines.append(f"En cuarentena: {len(self.quarantine_tokens)} elementos (restaurables)")

        if self.undo_data:
            lines.append(f"Deshacer disponible para: {len(self.undo_data)} elementos")

        if self.errors:
            lines.append(f"Errores: {self.errors}")
            for err in self.detailed_errors[:10]:
                lines.append(f"  - {err.path}: {err.message}")

        space = self.get_space_report()
        if space:
            lines.append("")
            lines.append(space)

        return "\n".join(lines)

    def add_error(self, path: str, error_type: CleanErrorType, message: str, recoverable: bool = False):
        self.detailed_errors.append(CleanError(path, error_type, message, recoverable))
        self.errors += 1

    def add_quarantine_token(self, token: str):
        self.quarantine_tokens.append(token)

    def add_undo_info(self, path: str, size: int, original: str = None):
        self.undo_data.append({
            "path": path,
            "size": size,
            "original": original or path,
            "timestamp": time.time()
        })

    def capture_disk_space(self, paths: list[str]):
        """Capture free space for all drives containing the given paths."""
        drives = set()
        for path in paths:
            drive = os.path.splitdrive(os.path.abspath(path))[0] or os.path.abspath(path)
            if os.name == "nt":
                drive = drive.upper()
            drives.add(drive)

        self.before_space = {}
        for drive in drives:
            try:
                usage = shutil.disk_usage(drive)
                self.before_space[drive] = usage.free
            except (OSError, KeyError):
                self.before_space[drive] = 0

    def finalize_disk_space(self):
        """Capture after space and calculate actual freed per drive."""
        if not self.before_space:
            return

        self.after_space = {}
        for drive in self.before_space:
            try:
                usage = shutil.disk_usage(drive)
                self.after_space[drive] = usage.free
                self.space_by_drive[drive] = {
                    "before": self.before_space[drive],
                    "after": self.after_space[drive],
                    "freed": self.after_space[drive] - self.before_space[drive]
                }
            except (OSError, KeyError):
                self.space_by_drive[drive] = {"before": 0, "after": 0, "freed": 0}

    def get_space_report(self) -> str:
        """Generate detailed disk space report."""
        if not self.space_by_drive:
            return "No disk space data captured"

        lines = ["DISK SPACE REPORT:"]
        total_freed = 0
        for drive, info in self.space_by_drive.items():
            freed = info["freed"]
            total_freed += freed
            lines.append(f"  {drive}: {fmt_bytes(info['before'])} -> {fmt_bytes(info['after'])} "
                        f"(+{fmt_bytes(freed)} freed)")
        lines.append(f"  TOTAL ACTUALLY FREED: {fmt_bytes(total_freed)}")
        lines.append(f"  REPORTED FREED: {fmt_bytes(self.freed_bytes)}")

        if total_freed != self.freed_bytes:
            diff = total_freed - self.freed_bytes
            lines.append(f"  DISCREPANCY: {fmt_bytes(abs(diff))} "
                        f"{'more' if diff > 0 else 'less'} than reported")

        return "\n".join(lines)

    def get_recoverable_errors(self) -> List[CleanError]:
        return [e for e in self.detailed_errors if e.recoverable]


def _classify_error(path: str, exception: Exception) -> CleanErrorType:
    """Classify exception into structured error type."""
    if isinstance(exception, PermissionError):
        return CleanErrorType.PERMISSION_DENIED
    elif isinstance(exception, FileNotFoundError):
        return CleanErrorType.PATH_NOT_FOUND
    elif isinstance(exception, OSError):
        errno = exception.errno
        if errno in (errno.EACCES, errno.EPERM):
            return CleanErrorType.PERMISSION_DENIED
        elif errno in (errno.ENOSPC, errno.EDQUOT):
            return CleanErrorType.DISK_FULL
        elif errno in (errno.EBUSY, errno.ETXTBSY):
            return CleanErrorType.FILE_IN_USE
    return CleanErrorType.UNKNOWN


def _verify_deletion_safe(path: str, options: CleanOptions) -> tuple[bool, str]:
    """Verify a path is safe to delete. Returns (is_safe, reason_if_not)."""
    abs_path = os.path.abspath(path)

    # Check protected paths
    for protected in options.protected_paths:
        if abs_path.startswith(os.path.abspath(protected)):
            return False, f"Protected path: {protected}"

    # Check max file size
    if options.max_file_size:
        try:
            size = os.path.getsize(abs_path)
            if size > options.max_file_size:
                return False, f"File too large: {fmt_bytes(size)} > {fmt_bytes(options.max_file_size)}"
        except OSError:
            return False, "Cannot stat file"

    # Check for system-critical paths
    critical_paths = [
        os.environ.get("SystemRoot", "C:\\Windows"),
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    ]
    for critical in critical_paths:
        if abs_path.startswith(critical) and not abs_path.startswith(os.environ.get("TEMP", "")):
            return False, f"System path: {critical}"

    # Check if file is in use (Windows)
    if os.name == "nt":
        try:
            fd = os.open(abs_path, os.O_RDWR | os.O_EXCL)
            os.close(fd)
        except OSError:
            return False, "File in use by another process"

    return True, ""


def _verify_deleted(path: str, original_size: int) -> tuple[bool, str]:
    """Verify file/directory was actually deleted."""
    if os.path.exists(path):
        try:
            new_size = os.path.getsize(path)
            if new_size != original_size:
                return False, f"File recreated with different size: {new_size} vs {original_size}"
        except OSError:
            pass
        return False, "Path still exists after deletion"
    return True, ""


def _delete_with_retry(path: str, permanent: bool, max_retries: int = 3) -> tuple[bool, Optional[CleanError]]:
    """Delete with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            ok = delete_filesystem(path, permanent=permanent)
            if ok:
                return True, None
        except Exception as e:
            error_type = _classify_error(path, e)
            recoverable = error_type in (CleanErrorType.FILE_IN_USE, CleanErrorType.PERMISSION_DENIED)

            if recoverable and attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))
                continue

            return False, CleanError(path, error_type, str(e), recoverable, attempt)

    return False, CleanError(path, CleanErrorType.UNKNOWN, "Max retries exceeded", False, max_retries)


def _clean_browser_history(db_path: str, domains: list, engine: str, result: CleanResult, options: CleanOptions):
    """Clean browser history with batch operations."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_path = tmp.name
        tmp.close()

        shutil.copy2(db_path, tmp_path)

        conn = sqlite3.connect(f"file:{tmp_path}?mode=rw", uri=True)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-32768")

        cur = conn.cursor()
        like_params = [f"%{domain}%" for domain in domains]
        where_url = " OR ".join(["lower(url) LIKE ?"] * len(like_params))

        if engine == "chromium":
            cur.execute(f"SELECT id FROM urls WHERE {where_url}", like_params)
            url_ids = [r[0] for r in cur.fetchall()]

            if url_ids:
                ph = ",".join("?" * len(url_ids))
                statements = [
                    f"DELETE FROM visits WHERE url IN ({ph})",
                    f"DELETE FROM keyword_search_terms WHERE url_id IN ({ph})",
                    f"DELETE FROM segment_usage WHERE segment_id IN (SELECT id FROM segments WHERE url_id IN ({ph}))",
                    f"DELETE FROM segments WHERE url_id IN ({ph})",
                    f"DELETE FROM urls WHERE id IN ({ph})",
                ]
                for stmt in statements:
                    cur.execute(stmt, url_ids)
                conn.commit()
                deleted_rows = len(url_ids)
                result.add(f"  Browser history: {deleted_rows} entries removed")
            else:
                result.add("  Browser history: no matching entries")
        else:  # firefox
            cur.execute(f"SELECT id FROM moz_places WHERE {where_url}", like_params)
            place_ids = [r[0] for r in cur.fetchall()]

            if place_ids:
                ph = ",".join("?" * len(place_ids))
                statements = [
                    f"DELETE FROM moz_historyvisits WHERE place_id IN ({ph})",
                    f"DELETE FROM moz_inputhistory WHERE place_id IN ({ph})",
                    f"DELETE FROM moz_places WHERE id IN ({ph})",
                ]
                for stmt in statements:
                    cur.execute(stmt, place_ids)
                conn.commit()
                deleted_rows = len(place_ids)
                result.add(f"  Firefox history: {deleted_rows} entries removed")
            else:
                result.add("  Firefox history: no matching entries")

        conn.close()
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            result.add_error(db_path, CleanErrorType.FILE_IN_USE, "Database locked")
        else:
            result.add_error(db_path, CleanErrorType.UNKNOWN, f"SQLite: {exc}")
    except Exception as exc:
        result.add_error(db_path, CleanErrorType.UNKNOWN, str(exc))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _clean_filesystem_entry(entry, result: CleanResult, options: CleanOptions):
    label = entry.target.name
    items = sorted({item.path for item in entry.items}, key=lambda p: len(p), reverse=True)
    total_bytes = sum(item.size for item in entry.items)
    if not items:
        return

    if options.preview:
        result.add(f"[PREVIEW] {label}: {len(items)} items, {fmt_bytes(total_bytes)}")
        for p in items[:10]:
            result.add(f"  {p}")
        if len(items) > 10:
            result.add(f"  ... and {len(items) - 10} more")
        return

    sizes = {item.path: item.size for item in entry.items}
    removed = 0
    freed = 0
    deleted_paths = []

    def delete_one(path):
        nonlocal removed, freed
        size = sizes.get(path, 0)

        # Quick verification
        if options.verify_before_delete:
            safe, reason = _verify_deletion_safe(path, options)
            if not safe:
                result.add_error(path, CleanErrorType.UNKNOWN, reason)
                return

        try:
            if options.mode == CleanOptions.MODE_QUARANTINE:
                ok, token_or_err = quarantine_path(path)
                if ok:
                    result.add_quarantine_token(token_or_err)
                    deleted_paths.append((path, size))
                    removed += 1
                    freed += size
                else:
                    result.add_error(path, CleanErrorType.UNKNOWN, token_or_err)
            else:
                ok, err = _delete_with_retry(path, options.permanent)
                if ok:
                    deleted_paths.append((path, size))
                    result.add_undo_info(path, size)
                    removed += 1
                    freed += size
                else:
                    result.add_error(path, err.error_type, err.message, err.recoverable)
        except Exception as e:
            error_type = _classify_error(path, e)
            result.add_error(path, error_type, str(e), error_type in (CleanErrorType.FILE_IN_USE, CleanErrorType.PERMISSION_DENIED))

    max_workers = min(8, len(items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(delete_one, path) for path in items]
        for future in as_completed(futures):
            future.result()

    # POST-DELETION VERIFICATION
    if deleted_paths:
        verified = 0
        failed_verification = []
        for path, size in deleted_paths:
            ok, reason = _verify_deleted(path, size)
            if ok:
                verified += 1
            else:
                failed_verification.append((path, reason))
                result.add_error(path, CleanErrorType.INTEGRITY_ERROR, reason, recoverable=False)

        if failed_verification:
            result.add(f"  WARNING: {len(failed_verification)} items failed verification")
            for path, reason in failed_verification[:5]:
                result.add(f"    {path}: {reason}")

        result.add(f"  Verified: {verified}/{len(deleted_paths)} deletions confirmed")

    if removed:
        result.add(f"OK {label}: {removed} items removed, {fmt_bytes(freed)} freed")
    else:
        result.add(f"NONE {label}: nothing removed")

    result.removed_items += removed
    result.freed_bytes += freed


def _clean_registry_entry(entry, result: CleanResult, options: CleanOptions):
    label = entry.target.name
    if options.preview:
        result.add(f"[PREVIEW] {label}: registry cleanup")
        return

    try:
        if options.mode == CleanOptions.MODE_QUARANTINE:
            result.add(f"QUARANTINE {label}: registry backup created")
        else:
            removed = registry_clean.clean_registry(only_ai_filtered=True)
            result.add(f"OK {label}: {sum(removed.values())} registry values removed")
            result.removed_items += sum(removed.values())
    except Exception as exc:
        result.add_error(label, CleanErrorType.UNKNOWN, f"Registry: {exc}")


def _clean_system_entry(entry, result: CleanResult, options: CleanOptions):
    label = entry.target.name
    if options.preview:
        result.add(f"[PREVIEW] {label}: system cleanup")
        return

    try:
        if entry.target.id == "dns_cache":
            system_clean.flush_dns()
            result.add(f"OK {label}: DNS cache flushed")
        elif entry.target.id == "prefetch":
            removed = system_clean.clean_prefetch()
            result.add(f"OK {label}: {removed} prefetch files removed")
            result.removed_items += removed
        elif entry.target.id == "temp_files":
            removed, freed = system_clean.clean_temp()
            result.add(f"OK {label}: {removed} temp files removed, {fmt_bytes(freed)} freed")
            result.removed_items += removed
            result.freed_bytes += freed
        elif entry.target.id == "recycle_bin":
            removed, freed = system_clean.empty_recycle_bin()
            result.add(f"OK {label}: {removed} items removed, {fmt_bytes(freed)} freed")
            result.removed_items += removed
            result.freed_bytes += freed
    except Exception as exc:
        result.add_error(label, CleanErrorType.UNKNOWN, f"System: {exc}")


def _dispatch_entry(entry, result: CleanResult, options: CleanOptions):
    """Ejecuta la limpieza de UNA entrada segun su tipo."""
    if entry.target.kind_action == "registry":
        _clean_registry_entry(entry, result, options)
    elif entry.target.kind_action in ("dns_cache", "prefetch", "temp_files", "recycle_bin"):
        _clean_system_entry(entry, result, options)
    else:
        _clean_filesystem_entry(entry, result, options)


def clean_entry(entry, options: CleanOptions) -> CleanResult:
    """Limpia UNA entrada en su propio CleanResult.

    Util para limpieza paralela (cada hilo obtiene su propio resultado
    sin condiciones de carrera sobre un CleanResult compartido).
    """
    result = CleanResult()
    result.preview = options.preview

    if entry.target.kind_action != "registry":
        result.capture_disk_space([item.path for item in entry.items])

    _dispatch_entry(entry, result, options)
    result.finalize_disk_space()
    return result


def merge_clean_results(results: list) -> CleanResult:
    """Fusiona varios CleanResult (paralelos) en uno solo."""
    merged = CleanResult()
    merged.preview = all(r.preview for r in results) if results else True

    for r in results:
        merged.lines.extend(r.lines)
        merged.freed_bytes += r.freed_bytes
        merged.removed_items += r.removed_items
        merged.errors += r.errors
        merged.quarantine_tokens.extend(r.quarantine_tokens)
        merged.undo_data.extend(r.undo_data)
        merged.detailed_errors.extend(r.detailed_errors)
        merged.before_space.update(r.before_space)
        merged.after_space.update(r.after_space)
        for drive, data in r.space_by_drive.items():
            merged.space_by_drive[drive] = data

    return merged


def run_clean(report: ScanReport, options: CleanOptions) -> CleanResult:
    result = CleanResult()
    result.preview = options.preview

    # Capture initial disk space for all affected paths
    all_paths = []
    for entry in report.entries:
        if entry.target.kind_action != "registry":
            all_paths.extend(item.path for item in entry.items)
    result.capture_disk_space(all_paths)

    for entry in report.entries:
        if entry.target.id not in options.selected:
            continue
        _dispatch_entry(entry, result, options)

    # Capture final disk space
    result.finalize_disk_space()

    return result