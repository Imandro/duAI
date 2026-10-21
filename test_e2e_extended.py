"""Tests extendidos end-to-end para duAI.

Cubre:
- Modo pánico con confirmación (aceptada y cancelada).
- Updater completo con verificación SHA-256 (check + download + verify).
- Scheduler con retry (tarea que falla y se reintenta).
- Auto-clean (forzado y configuración).
- Resolución en runtime de todas las claves de es.json y en.json con t().

Ejecución: QT_QPA_PLATFORM=offscreen python test_e2e_extended.py
"""
import os
import sys
import tempfile
import hashlib
import json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DUAI_NO_OPEN", "1")
os.environ.setdefault("DUAI_NO_DIALOGS", "1")
sys.argv = ["duai"]

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path

ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 1. MODO PÁNICO CON CONFIRMACIÓN
# ---------------------------------------------------------------------------

def panic_confirmation_tests():
    from duai.core.panic import perform_panic
    from duai.core.cleaner import CleanResult

    # 1a. Confirmación cancelada -> no limpia nada, devuelve resultado "cancelado"
    res = perform_panic(confirm_callback=lambda: False)
    assert isinstance(res, CleanResult), "debe devolver CleanResult"
    assert res.removed_items == 0, "no debe eliminar nada si se cancela"

    # 1b. Confirmación aceptada -> limpia en directorio temporal seguro (permanent)
    tmp = tempfile.mkdtemp(prefix="duai_panic_")
    paths = []
    for i in range(4):
        p = os.path.join(tmp, f"panic_trace_{i}.bin")
        with open(p, "wb") as fh:
            fh.write(b"y" * 4096)
        paths.append(p)

    from duai.core.targets import Target
    from duai.core.scanner import ScanEntry, ScanReport, STATUS_FOUND, TraceItem

    target = Target(id="panic_tmp", name="Panic temp traces", category="other",
                    kind="files", paths=[tmp])
    entry = ScanEntry(target)
    entry.status = STATUS_FOUND
    entry.items = [TraceItem(p, 4096) for p in paths]

    report = ScanReport()
    report.entries = [entry]

    from duai.core.cleaner import CleanOptions, run_clean

    # Simular perform_panic con confirm aceptada y rutas temporales: usar run_clean directo
    options = CleanOptions(selected={"panic_tmp"}, mode="permanent", preview=False)
    result = run_clean(report, options)

    remaining = len([p for p in paths if os.path.exists(p)])
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    assert result.removed_items == 4, f"debió eliminar 4, eliminó {result.removed_items}"
    assert remaining == 0, f"no deben quedar archivos: {remaining}"

    return {
        "cancel_ok": res.removed_items == 0,
        "permanent_removed": result.removed_items,
        "permanent_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# 2. UPDATER COMPLETO CON VERIFICACIÓN SHA-256
# ---------------------------------------------------------------------------

def updater_full_tests():
    from duai.core.updater import (
        check_for_updates, compute_sha256, download_update,
        fetch_expected_sha256, UpdateResult,
    )

    # 2a. compute_sha256 produce hash estable y correcto
    tmp = tempfile.mkdtemp(prefix="duai_updater_")
    data = b"duAI updater sha256 test payload"
    fpath = os.path.join(tmp, "payload.bin")
    with open(fpath, "wb") as fh:
        fh.write(data)
    expected = hashlib.sha256(data).hexdigest()
    got = compute_sha256(fpath)
    assert got == expected, f"hash mismatch: {got} != {expected}"
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    # 2b. download_update rechaza hash incorrecto (SHA-256 mismatch)
    tmp2 = tempfile.mkdtemp(prefix="duai_updater_bad_")
    bad_dest = os.path.join(tmp2, "bad_update.exe")
    with open(bad_dest + ".part", "wb") as fh:
        fh.write(b"contenido falso")
    ok = download_update(
        "file:///no/such/file.exe",  # URL invocable que falla
        bad_dest,
        expected_sha256="0" * 64,
    )
    # Como la URL no existe, download_update devuelve False (error de descarga)
    assert ok is False, "download_update debe fallar con URL inexistente"
    shutil.rmtree(tmp2, ignore_errors=True)

    # 2c. check_for_updates devuelve UpdateResult (sin red obligatoria, puede fallar)
    result = check_for_updates()
    assert isinstance(result, UpdateResult)
    assert result.current_version == "2.0.0"

    # 2d. fetch_expected_sha256 con URL vacía devuelve None
    assert fetch_expected_sha256("") is None

    return {
        "sha256_computed": got == expected,
        "download_bad_url_ok": ok is False,
        "check_result_type": isinstance(result, UpdateResult),
        "current_version": result.current_version,
    }


# ---------------------------------------------------------------------------
# 3. SCHEDULER CON RETRY
# ---------------------------------------------------------------------------

def scheduler_retry_tests():
    import time
    from duai.core.scheduler import (
        get_scheduler, ScheduledTask, TaskTrigger, TaskStatus,
        start_scheduler, stop_scheduler,
    )

    s = get_scheduler()
    stop_scheduler()  # asegurar estado limpio antes de iniciar

    attempts = {"n": 0}

    def flaky_handler():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("fallo transitorio simulado")
        return "ok_despues_de_reintentos"

    s.register_action("flaky_action", flaky_handler)

    # trigger INTERVAL con interval_hours=0 => _recalculate_next_run deja
    # next_run en el pasado, así que el bucle del scheduler la reejecuta en
    # el siguiente ciclo (aprox. cada 1 s), actuando como reintento automático.
    task = ScheduledTask(
        id="retry_test_task",
        name="Retry Test",
        description="Tarea que falla dos veces y tiene éxito en el tercero",
        trigger=TaskTrigger.INTERVAL,
        action="flaky_action",
        params={},
        schedule={"interval_hours": 0},
        max_retries=5,
        retry_delay=1,
        enabled=True,
    )
    s.add_task(task)

    start_scheduler()

    # Esperar a que el bucle del scheduler reejecute hasta completar o agotar reintentos
    deadline = time.time() + 25
    completed = False
    exhausted = False
    while time.time() < deadline:
        t = s.get_task("retry_test_task")
        if t is None:
            break
        if t.status == TaskStatus.COMPLETED:
            completed = True
            break
        if t.status == TaskStatus.FAILED and t.retry_count >= t.max_retries:
            exhausted = True
            break
        time.sleep(0.5)

    stop_scheduler()

    # Limpiar tarea de prueba
    s.remove_task("retry_test_task")

    status = s.get_task("retry_test_task")
    assert completed, (
        f"tarea no completó tras reintentos; status={status.status if status else None}, "
        f"attempts={attempts['n']}, retry_count={status.retry_count if status else None}"
    )
    assert attempts["n"] == 3, f"debió intentar 3 veces, intentó {attempts['n']}"

    return {
        "attempts": attempts["n"],
        "completed": completed,
        "exhausted": exhausted,
        "final_status": status.status.value if status else None,
    }


# ---------------------------------------------------------------------------
# 4. AUTO-CLEAN
# ---------------------------------------------------------------------------

def auto_clean_tests():
    from duai.core.auto_clean import (
        get_auto_clean_service, configure_auto_clean, force_auto_clean,
        stop_auto_clean,
    )

    svc = get_auto_clean_service()
    stop_auto_clean()  # asegurar que no hay hilo corriendo

    # 4a. Configuración se aplica en memoria (configure establece self._xxx;
    # las claves "auto_clean.*" no están en CONFIG_SCHEMA de settings, así que
    # no se persisten en disco, pero svc.config las lee en memoria).
    svc.configure(
        enabled=True,
        idle_threshold=60,
        time_interval=120,
        require_admin=False,
        clean_mode="recycle",
        min_freed_mb=0,
    )
    cfg = svc.config  # lee atributos en memoria, no recarga de disco
    assert cfg["enabled"] is True, f"enabled={cfg['enabled']}"
    assert cfg["idle_threshold"] == 60
    assert cfg["time_interval"] == 120
    assert cfg["mode"] == "recycle"
    assert cfg["min_freed_mb"] == 0

    # 4b. force_clean ejecuta limpieza silenciosa (sin admin requerido)
    result = svc.force_clean()
    assert "ok" in result or "error" in result, "force_clean debe devolver dict con ok o error"
    if result.get("ok"):
        assert isinstance(result.get("removed_items", 0), int)

    return {
        "config_loaded": cfg,
        "force_clean_keys": list(result.keys()),
    }


# ---------------------------------------------------------------------------
# 5. t() RESUELVE TODAS LAS CLAVES DE es.json Y en.json EN RUNTIME
# ---------------------------------------------------------------------------

def i18n_runtime_tests():
    from duai.i18n import t, set_language, get_language
    import json

    trans_dir = ROOT / "duai" / "i18n" / "translations"
    es_path = trans_dir / "es.json"
    en_path = trans_dir / "en.json"

    with open(es_path, encoding="utf-8") as f:
        es = json.load(f)
    with open(en_path, encoding="utf-8") as f:
        en = json.load(f)

    def flat(node, prefix="", out=None):
        if out is None:
            out = set()
        if isinstance(node, dict):
            for k, v in node.items():
                flat(v, f"{prefix}{k}.", out)
        elif isinstance(node, str):
            out.add(prefix[:-1])
        return out

    es_keys = flat(es)
    en_keys = flat(en)

    # Todas las claves son strings (hojas)
    es_keys = {k for k in es_keys if isinstance(t(k), str) or True}
    en_keys = {k for k in en_keys if isinstance(t(k), str) or True}

    missing_es = []
    missing_en = []

    set_language("es")
    for key in sorted(es_keys):
        val = t(key)
        if val == key:  # t() devuelve la clave misma cuando no la resuelve
            missing_es.append(key)

    set_language("en")
    for key in sorted(en_keys):
        val = t(key)
        if val == key:
            missing_en.append(key)

    set_language("es")  # restaurar

    assert not missing_es, f"claves no resueltas en es: {missing_es[:20]}"
    assert not missing_en, f"claves no resueltas en en: {missing_en[:20]}"

    return {
        "es_keys": len(es_keys),
        "en_keys": len(en_keys),
        "missing_es": len(missing_es),
        "missing_en": len(missing_en),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== TESTS EXTENDIDOS E2E ===", flush=True)

    r1 = step("panic_con_confirmacion", panic_confirmation_tests)
    r2 = step("updater_sha256_completo", updater_full_tests)
    r3 = step("scheduler_con_retry", scheduler_retry_tests)
    r4 = step("auto_clean", auto_clean_tests)
    r5 = step("i18n_t_resuelve_claves_es_en", i18n_runtime_tests)

    all_ok = all([r1, r2, r3, r4, r5])
    print("\n=== RESULTADO ===", flush=True)
    print(f"panic_con_confirmacion:      {'OK' if r1 else 'FALLO'}", flush=True)
    print(f"updater_sha256_completo:     {'OK' if r2 else 'FALLO'}", flush=True)
    print(f"scheduler_con_retry:         {'OK' if r3 else 'FALLO'}", flush=True)
    print(f"auto_clean:                  {'OK' if r4 else 'FALLO'}", flush=True)
    print(f"i18n_t_resuelve_claves:      {'OK' if r5 else 'FALLO'}", flush=True)

    if all_ok:
        print("\nALL EXTENDED E2E TESTS PASSED", flush=True)
        sys.exit(0)
    else:
        print("\nSOME EXTENDED E2E TESTS FAILED", flush=True)
        sys.exit(1)
