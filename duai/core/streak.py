"""Sistema de racha (streak) de privacidad.

Cuenta los dias consecutivos en los que el usuario ha mantenido
su equipo libre de rastros de IA. Es un feature de gamificacion
que mantiene al usuario regresando a duAI.
"""

import json
import os
from datetime import datetime, timedelta

from ..utils.logger import base_dir


def _streak_path():
    return os.path.join(base_dir(), "streak.json")


def _load():
    path = _streak_path()
    if not os.path.exists(path):
        return {"current": 0, "best": 0, "last_clean_date": None, "history": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"current": 0, "best": 0, "last_clean_date": None, "history": []}


def _save(data):
    path = _streak_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def get_streak():
    """Devuelve el estado actual de la racha."""
    return _load()


def update_streak(found_count):
    """Actualiza la racha basada en el resultado del escaneo.

    Si found_count == 0, la racha sube.
    Si found_count > 0, la racha se reinicia a 0.
    """
    data = _load()
    today = datetime.now().date().isoformat()

    if found_count == 0:
        # Dia limpio
        last = data.get("last_clean_date")
        if last == today:
            # Ya se registro hoy, no duplicar
            return data
        if last:
            last_date = datetime.fromisoformat(last).date()
            if (datetime.now().date() - last_date).days == 1:
                # Dia consecutivo
                data["current"] += 1
            elif (datetime.now().date() - last_date).days > 1:
                # Racha rota
                data["current"] = 1
            # Si es el mismo dia, no cambiar
        else:
            data["current"] = 1

        data["last_clean_date"] = today
        if data["current"] > data.get("best", 0):
            data["best"] = data["current"]

        # Agregar al historial
        data.setdefault("history", []).append({
            "date": today,
            "clean": True,
            "streak": data["current"],
        })
    else:
        # Rastros encontrados: reiniciar racha
        data["current"] = 0
        data.setdefault("history", []).append({
            "date": today,
            "clean": False,
            "found": found_count,
        })

    # Mantener historial de 90 dias
    if len(data.get("history", [])) > 90:
        data["history"] = data["history"][-90:]

    _save(data)
    return data


def get_streak_message():
    """Devuelve un mensaje descriptivo de la racha."""
    data = _load()
    current = data.get("current", 0)
    best = data.get("best", 0)

    if current == 0:
        return "Sin racha activa. Escanea y limpia para empezar."
    if current == 1:
        return "1 dia limpio. Sigue asi!"
    if current < 7:
        return f"{current} dias limpios. Vas bien!"
    if current < 30:
        return f"{current} dias limpios. Racha semanal!"
    if current < 90:
        return f"{current} dias limpios. Racha mensual!"
    return f"{current} dias limpios. Racha legendaria!"


def get_streak_emoji():
    """Devuelve texto representativo de la racha (sin emojis)."""
    data = _load()
    current = data.get("current", 0)
    if current == 0:
        return "SIN RACHA"
    if current < 7:
        return "INICIO"
    if current < 30:
        return "ACTIVA"
    if current < 90:
        return "FUERTE"
    return "LEGENDARIA"
