"""Test: panic (con confirmacion), quick_clean, updater, scheduler, selfclean."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DUAI_NO_OPEN", "1")
sys.argv = ["duai"]

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def step(name, fn):
    print(f"--- {name} ...", flush=True)
    try:
        out = fn()
        print(f"    OK: {out}", flush=True)
        return out
    except Exception:
        import traceback
        print("    FAIL:", flush=True)
        traceback.print_exc()
        return None


# PANIC (solo la ruta de confirmacion cancelada; la ruta destructiva se
# prueba con un reporte sintetico en un directorio temporal seguro)
step("panic_cancel", lambda: __import__("duai.core.panic", fromlist=["x"]).perform_panic(
    confirm_callback=lambda: False).summary())

def parallel_clean_tmp():
    import shutil
    import tempfile

    from duai.core.targets import Target
    from duai.core.scanner import ScanEntry, ScanReport, STATUS_FOUND, TraceItem
    from duai.core.cleaner import CleanOptions, clean_entry, merge_clean_results
    from duai.core.panic import _parallel_clean_targets

    tmp = tempfile.mkdtemp(prefix="duai_test_")
    paths = []
    for i in range(6):
        p = os.path.join(tmp, f"trace_{i}.log")
        with open(p, "wb") as fh:
            fh.write(b"x" * 2048)
        paths.append(p)

    target = Target(id="tmp_test", name="Temp traces", category="other",
                    kind="files", paths=[tmp])
    entry = ScanEntry(target)
    entry.status = STATUS_FOUND
    entry.items = [TraceItem(p, 2048) for p in paths]

    report = ScanReport()
    report.entries = [entry]

    options = CleanOptions(selected={"tmp_test"}, mode="permanent", preview=False)
    merged = _parallel_clean_targets(report, options, max_workers=3)
    remaining = len([p for p in paths if os.path.exists(p)])
    shutil.rmtree(tmp, ignore_errors=True)
    return {"removed": merged.removed_items, "freed": merged.freed_bytes,
            "remaining": remaining, "lines": len(merged.lines)}

step("panic_parallel_clean", parallel_clean_tmp)

# QUICK CLEAN
step("quick_clean", lambda: __import__("duai.core.quick_clean", fromlist=["x"]).run_quick_clean())

# UPDATER: firma, historial, rollback
def updater_bits():
    from duai.core.updater import (
        CURRENT_VERSION, get_update_history, add_update_history,
        clear_update_history, RollbackManager, verify_signature,
    )
    h = get_update_history()
    add_update_history({"version": "9.9.9", "timestamp": "2026-01-01 00:00:00", "status": "test"})
    h2 = get_update_history()
    ok_sig = verify_signature(b"hello", b"\x00" * 64)  # clave no configurada -> skip
    rm = RollbackManager()
    backups = rm.list_backups()
    clear_update_history()
    return {"version": CURRENT_VERSION, "history_before": len(h),
            "history_after": len(h2), "sig_skipped": ok_sig,
            "rollback_backups": len(backups)}
step("updater", updater_bits)

# SCHEDULER
def sched_bits():
    from duai.core.scheduler import (
        get_scheduler, HotkeyWorker, create_logon_task,
        remove_logon_task, logon_task_exists, stop_scheduler,
    )
    s = get_scheduler()
    status = s.get_status()
    tasks = s.list_tasks()
    exists = logon_task_exists()  # solo consulta
    stop_scheduler()
    return {"status": status, "tasks": len(tasks), "logon_exists": exists}
step("scheduler", sched_bits)

# SELFCLEAN
step("selfclean_backups", lambda: len(__import__("duai.core.selfclean", fromlist=["x"]).list_self_backups()))
step("selfclean_verify", lambda: __import__("duai.core.selfclean", fromlist=["x"]).verify_clean())

# REGISTRY (dry-run, seguro)
def reg_bits():
    from duai.core.registry_clean import clean_registry, list_backups
    res = clean_registry(ai_only=True, dry_run=True, create_backup=False)
    return {"removed": res, "backups": len(list_backups())}
step("registry_dryrun", reg_bits)

# AUTO CLEAN (sin iniciar)
def autoclean_bits():
    from duai.core.auto_clean import get_auto_clean_service, stop_auto_clean
    svc = get_auto_clean_service()
    cfg = svc.load_config() if hasattr(svc, "load_config") else None
    stop_auto_clean()
    return {"config": cfg}
step("autoclean", autoclean_bits)

# LEADERBOARD
step("leaderboard", lambda: __import__("duai.core.leaderboard", fromlist=["x"]).get_tier_distribution())

# BROWSER EXTENSION archivos validos
import json
def ext_bits():
    base = os.path.join(os.path.dirname(__file__), "browser_extension")
    names = ["manifest.json"]
    loaded = {}
    for n in names:
        with open(os.path.join(base, n), encoding="utf-8") as fh:
            loaded[n] = json.load(fh)
    files = os.listdir(base)
    return {"files": sorted(files), "manifest_version": loaded["manifest.json"]["manifest_version"]}
step("browser_extension", ext_bits)

print("\nALL MODULE TESTS DONE", flush=True)
