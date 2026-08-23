from .cleaner import CleanOptions, run_clean
from .browser_tabs import close_ai_tabs
from .scanner import scan_targets
from ..utils.logger import log
from ..utils.paths import is_admin
from ..utils.settings import get_settings

_VALID_MODES = ("recycle", "permanent", "quarantine")


def _panic_mode(settings, permanent=None):
    if permanent is True:
        return "permanent"
    mode = settings.get("panic_mode")
    return mode if mode in _VALID_MODES else "recycle"


def perform_panic(progress=None, permanent=None, mode=None):
    settings = get_settings()
    clean_mode = mode if mode in _VALID_MODES else _panic_mode(settings, permanent)

    tab_report = close_ai_tabs()
    tabs_closed = tab_report.get("closed", 0)

    admin = is_admin()
    targets = build_safe_targets(settings, admin)
    report = scan_targets(targets)

    selected = set()
    for entry in report.entries:
        if entry.status in ("found", "ready"):
            selected.add(entry.target.id)

    options = CleanOptions(selected=selected, mode=clean_mode, preview=False)
    result = run_clean(report, options)
    result.tabs_closed = tabs_closed
    log("panic", removed=result.removed_items, freed_bytes=result.freed_bytes,
        errors=result.errors, mode=clean_mode, tabs_closed=tabs_closed)
    if progress:
        progress(result)
    return result


def build_safe_targets(settings, admin):
    from .targets import build_targets

    exclusions = set(settings.get("exclusions") or [])
    targets = build_targets(exclusions=exclusions)
    if not admin:
        targets = [t for t in targets if not t.requires_admin]
    return targets


def perform_silent_clean(permanent=True, progress=None, mode=None):
    settings = get_settings()
    admin = is_admin()
    targets = build_safe_targets(settings, admin)
    report = scan_targets(targets)
    selected = {
        entry.target.id
        for entry in report.entries
        if entry.status in ("found", "ready")
        and not entry.target.requires_admin
    }
    clean_mode = mode or ("permanent" if permanent else "recycle")
    options = CleanOptions(selected=selected, mode=clean_mode, preview=False)
    result = run_clean(report, options)
    log("auto_clean", removed=result.removed_items, freed_bytes=result.freed_bytes,
        errors=result.errors)
    if progress:
        progress(result)
    return result


def format_result_summary(result):
    lines = [result.summary(), ""]
    tabs = getattr(result, "tabs_closed", 0)
    if tabs:
        lines.append(f"PESTAÑAS DE IA CERRADAS: {tabs}")
    lines.extend(result.lines)
    return "\n".join(lines)
