"""Calculo de Privacy Score (0-100) para duAI.

El Privacy Score es un numero unico que resume el estado de privacidad
del usuario. Cuanto mas alto, mejor. Se calcula a partir del ultimo
escaneo: rastros encontrados, apps de IA, historial de navegador, etc.

Es el feature mas viral de duAI: "Mi Privacy Score es 95/100".
"""

import json
import os
from datetime import datetime

from . import reporter


def _base_dir():
    from ..utils.logger import base_dir
    return base_dir()


def _score_path():
    return os.path.join(_base_dir(), "privacy_score.json")


def _load_history():
    path = _score_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(history):
    path = _score_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)


def calculate_score(report=None):
    """Calcula el Privacy Score (0-100) a partir de un reporte de escaneo.

    Factores que reducen el score:
    - Rastros encontrados (archivos, registro, historial, etc.)
    - Apps de IA instaladas
    - Historial de navegador con sitios de IA
    - Entradas de registro de Windows
    - Cache DNS con dominios de IA
    - Portapapeles con texto de IA
    - Timeline / ubicacion

    Factores que aumentan el score:
    - Modo sigilo activo
    - Bloqueo de hosts activo
    - Cuarentena vacia
    - Sin apps de IA instaladas
    """
    if report is None:
        # Sin reporte: score neutro
        return 50

    score = 100

    # Penalizar por rastros encontrados
    found = len(report.found_entries) if hasattr(report, "found_entries") else 0
    total = len(report.entries) if hasattr(report, "entries") else 1
    if total > 0:
        ratio = found / total
        score -= int(ratio * 40)  # hasta -40 puntos por rastros

    # Penalizar por bytes de rastros
    total_bytes = getattr(report, "total_bytes", 0)
    if total_bytes > 0:
        # 1 MB = -2 pts, max -20
        mb = total_bytes / (1024 * 1024)
        score -= min(20, int(mb * 2))

    # Penalizar por items encontrados
    total_items = 0
    for entry in getattr(report, "entries", []):
        if entry.status if hasattr(entry, "status") else None:
            pass
        items = getattr(entry, "items", [])
        if items:
            total_items += len(items)
    score -= min(15, total_items // 5)  # hasta -15 por items

    # Bonus por modo sigilo
    try:
        from ..utils.settings import get_settings
        if get_settings().get("self_purge_on_exit"):
            score += 5
        if get_settings().get("hosts_block"):
            score += 5
    except Exception:
        pass

    # Bonus por cuarentena vacia
    try:
        from .quarantine import quarantined_items
        if not quarantined_items():
            score += 3
    except Exception:
        pass

    # Clamp 0-100
    score = max(0, min(100, score))
    return score


def score_label(score):
    """Devuelve una etiqueta descriptiva para el score."""
    if score >= 90:
        return "EXCELENTE"
    if score >= 70:
        return "BUENO"
    if score >= 50:
        return "REGULAR"
    if score >= 30:
        return "BAJO"
    return "CRITICO"


def score_color(score):
    """Devuelve un color para el score (para UI)."""
    if score >= 90:
        return "#00FF40"
    if score >= 70:
        return "#FFFFFF"
    if score >= 50:
        return "#9A9A9A"
    if score >= 30:
        return "#FF8800"
    return "#FF0040"


def record_score(score, report=None):
    """Guarda el score en el historial para tracking de tendencias."""
    history = _load_history()
    entry = {
        "score": score,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "found_entries": len(report.found_entries) if report and hasattr(report, "found_entries") else 0,
        "total_bytes": getattr(report, "total_bytes", 0) if report else 0,
    }
    history.append(entry)
    # Mantener solo los ultimos 90 dias
    if len(history) > 90:
        history = history[-90:]
    _save_history(history)
    return entry


def get_latest_score():
    """Devuelve el ultimo score registrado."""
    history = _load_history()
    if not history:
        return None
    return history[-1]


def get_score_trend(days=7):
    """Devuelve la tendencia de score en los ultimos N dias."""
    history = _load_history()
    if not history:
        return []
    return history[-days:]


def get_best_score():
    """Devuelve el mejor score historico."""
    history = _load_history()
    if not history:
        return None
    return max(h["score"] for h in history)


def get_average_score():
    """Devuelve el score promedio."""
    history = _load_history()
    if not history:
        return None
    return sum(h["score"] for h in history) // len(history)


def generate_score_report(score):
    """Genera un reporte de texto para compartir en redes."""
    label = score_label(score)
    lines = [
        "duAI — Privacy Score Report",
        f"Privacy Score: {score}/100 ({label})",
        "",
        "Escanea y elimina rastros de 30+ apps de IA.",
        "100% local. Sin telemetria. Sin cuentas.",
        "",
        "https://github.com/Imandro/duAI",
    ]
    return "\n".join(lines)
