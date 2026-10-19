"""Funciones virales y gamificacion para duAI.

Incluye:
- Generacion de reporte compartible (sin datos sensibles) para redes sociales.
- Sistema de logros/medallas basado en estadisticas de uso.
- Contador de racha y totales acumulados.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime

from ..utils.logger import base_dir, log
from ..utils.paths import fmt_bytes
from ..utils.settings import get_settings

STATS_FILE = os.path.join(base_dir(), "stats.json")

ACHIEVEMENTS = [
    {
        "id": "first_scan",
        "name": "Primer escaneo",
        "desc": "Realiza tu primer escaneo de rastros de IA.",
        "condition": lambda s: s.get("scans", 0) >= 1,
    },
    {
        "id": "panic_user",
        "name": "Modo Panico",
        "desc": "Ejecuta el boton de panico por primera vez.",
        "condition": lambda s: s.get("panics", 0) >= 1,
    },
    {
        "id": "gigabyte_freed",
        "name": "1 GB liberado",
        "desc": "Libera mas de 1 GB de espacio.",
        "condition": lambda s: s.get("total_freed_bytes", 0) >= 1024 ** 3,
    },
    {
        "id": "week_streak",
        "name": "Racha semanal",
        "desc": "Usa duAI durante 7 dias seguidos.",
        "condition": lambda s: s.get("streak_days", 0) >= 7,
    },
    {
        "id": "stealth_master",
        "name": "Modo Sigilo",
        "desc": "Activa el modo sigilo y cierra duAI 5 veces.",
        "condition": lambda s: s.get("stealth_exits", 0) >= 5,
    },
    {
        "id": "quarantine_king",
        "name": "Rey de la cuarentena",
        "desc": "Restaura 10 elementos de la cuarentena.",
        "condition": lambda s: s.get("quarantine_restores", 0) >= 10,
    },
]


class Stats:
    """Estadisticas acumuladas de uso de duAI."""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {
                "scans": 0,
                "cleans": 0,
                "panics": 0,
                "total_freed_bytes": 0,
                "total_items_removed": 0,
                "streak_days": 0,
                "stealth_exits": 0,
                "quarantine_restores": 0,
                "achievements_unlocked": [],
            }

    def save(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def increment(self, key, amount=1):
        self._data[key] = self._data.get(key, 0) + amount
        self.save()

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def record_scan(self, found: int, freed_bytes: int):
        if not get_settings().get("gamification", True):
            return
        self.increment("scans")
        # Streak basado en sesion actual (no se guarda fecha exacta para evitar perfilamiento)
        self._data["streak_days"] = self._data.get("streak_days", 0) + 1
        self.save()

    def record_clean(self, removed_items: int, freed_bytes: int):
        if not get_settings().get("gamification", True):
            return
        self.increment("cleans")
        self.increment("total_items_removed", removed_items)
        self.increment("total_freed_bytes", freed_bytes)
        self.save()

    def record_panic(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("panics")
        self.save()

    def record_stealth_exit(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("stealth_exits")
        self.save()

    def record_quarantine_restore(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("quarantine_restores")
        self.save()

    def unlocked_achievements(self):
        unlocked = set(self._data.get("achievements_unlocked", []))
        result = []
        for ach in ACHIEVEMENTS:
            result.append({
                **ach,
                "unlocked": ach["id"] in unlocked,
            })
        return result

    def unlock_achievement(self, ach_id: str) -> bool:
        if not get_settings().get("gamification", True):
            return False
        unlocked = set(self._data.get("achievements_unlocked", []))
        if ach_id in unlocked:
            return False
        unlocked.add(ach_id)
        self._data["achievements_unlocked"] = sorted(unlocked)
        self.save()
        return True

    def check_achievements(self):
        """Revisa y desbloquea logros segun estadisticas actuales."""
        if not get_settings().get("gamification", True):
            return []
        newly = []
        for ach in ACHIEVEMENTS:
            if ach["id"] not in set(self._data.get("achievements_unlocked", [])):
                if ach["condition"](self._data):
                    self.unlock_achievement(ach["id"])
                    newly.append(ach)
        return newly


_stats = None


def get_stats() -> Stats:
    global _stats
    if _stats is None:
        _stats = Stats()
    return _stats


def gamification_enabled() -> bool:
    """Indica si la gamificacion y registro de estadisticas esta activada."""
    return bool(get_settings().get("gamification", True))


def set_gamification(enabled: bool):
    """Activa o desactiva la gamificacion y registro de estadisticas."""
    get_settings().set("gamification", bool(enabled))


def reset_stats():
    """Reinicia todas las estadisticas y logros."""
    global _stats
    if _stats is not None:
        _stats._data = {
            "scans": 0,
            "cleans": 0,
            "panics": 0,
            "total_freed_bytes": 0,
            "total_items_removed": 0,
            "streak_days": 0,
            "stealth_exits": 0,
            "quarantine_restores": 0,
            "achievements_unlocked": [],
        }
        _stats.save()


def generate_share_report(scan_result=None, clean_result=None) -> str:
    """Genera un reporte corto y sin datos sensibles para compartir en redes."""
    stats = get_stats()
    lines = []

    lines.append("duAI — Don't Use AI")
    lines.append("=" * 30)
    lines.append("")

    if scan_result:
        found = len(getattr(scan_result, "found_entries", []) or [])
        total_bytes = getattr(scan_result, "total_bytes", 0)
        lines.append(f"Rastros de IA detectados: {found}")
        if total_bytes:
            lines.append(f"Espacio en riesgo: {fmt_bytes(total_bytes)}")
        lines.append("")

    if clean_result:
        lines.append(f"Elementos limpiados: {getattr(clean_result, 'removed_items', 0)}")
        freed = getattr(clean_result, "freed_bytes", 0)
        if freed:
            lines.append(f"Espacio liberado: {fmt_bytes(freed)}")
        lines.append("")

    lines.append(f"Total historico liberado: {fmt_bytes(stats.get('total_freed_bytes', 0))}")
    lines.append(f"Escaneos realizados: {stats.get('scans', 0)}")
    lines.append(f"Limpiezas realizadas: {stats.get('cleans', 0)}")
    lines.append("")
    lines.append("100% local. Sin telemetria. Sin cuentas.")
    lines.append("#duAI #Privacidad #DonTUseAI")

    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    """Copia texto al portapapeles de Windows."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            h_global = kernel32.GlobalAlloc(0x0002, len(text) + 1)
            if not h_global:
                return False
            locked = kernel32.GlobalLock(h_global)
            if not locked:
                kernel32.GlobalFree(h_global)
                return False
            ctypes.memmove(locked, text.encode("utf-16-le"), len(text) * 2 + 2)
            kernel32.GlobalUnlock(h_global)
            user32.SetClipboardData(13, h_global)  # CF_UNICODETEXT
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def open_share_url(platform: str, text: str) -> str:
    """Devuelve la URL para compartir en una plataforma determinada."""
    import urllib.parse

    encoded = urllib.parse.quote(text)
    if platform == "twitter":
        return f"https://twitter.com/intent/tweet?text={encoded}"
    if platform == "telegram":
        return f"https://t.me/share/url?url={encoded}"
    if platform == "whatsapp":
        return f"https://wa.me/?text={encoded}"
    if platform == "facebook":
        return f"https://www.facebook.com/sharer/sharer.php?u={encoded}"
    return f"https://twitter.com/intent/tweet?text={encoded}"
