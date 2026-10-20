"""Limpieza rapida en un solo clic.

Combina escaneo + limpieza con opciones por defecto:
- Todos los objetivos (sin exclusiones)
- Modo papelera (reversible)
- Vista previa desactivada (ejecucion directa)

Es el feature de "un clic y listo" para viralidad.
"""

import time
from ..core import scanner, targets
from ..utils.settings import get_settings


def run_quick_clean(progress_cb=None):
    """Ejecuta un escaneo completo seguido de limpieza en modo papelera.

    Args:
        progress_cb: callback(current, total, name) para progreso

    Returns:
        dict con resultados: found, cleaned, freed_bytes, elapsed
    """
    start = time.time()
    exclusions = set(get_settings().get("exclusions") or [])
    target_list = targets.build_targets(exclusions=exclusions)

    # Escanear
    report = scanner.scan_targets_parallel(target_list, progress_cb=progress_cb)

    found = len(report.found_entries)
    total_bytes = report.total_bytes

    # Limpiar en modo papelera
    from ..core.cleaner import CleanOptions, run_clean
    options = CleanOptions(
        selected=set(t.id for t in target_list),
        mode="recycle",
        preview=False,
    )
    result = run_clean(report, options)

    elapsed = time.time() - start

    return {
        "found": found,
        "cleaned": result.removed_items,
        "freed_bytes": result.freed_bytes,
        "elapsed": elapsed,
        "report": report,
        "result": result,
    }
