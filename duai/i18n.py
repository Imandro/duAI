"""Internacionalización para duAI - Archivos externos, pluralización, fallbacks."""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .utils.settings import get_settings


class I18nManager:
    """Gestiona traducciones con soporte para:
    - Archivos JSON externos
    - Namespaces anidados (nav.resumen, app.title)
    - Pluralización por idioma
    - Cadena de fallback (es-MX → es → en)
    - Contexto/desambiguación
    - Carga dinámica de idiomas
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._translations: Dict[str, Dict] = {}
        self._plural_rules: Dict[str, callable] = {}
        self._current_lang: str = "es"
        self._fallback_chain: Dict[str, List[str]] = {}
        self._load_all_translations()
        self._initialized = True

    def _get_translations_dir(self) -> Path:
        """Obtiene directorio de traducciones (soporta frozen/ejecutable)."""
        import sys as _sys

        if getattr(_sys, "frozen", False):
            base = Path(_sys._MEIPASS) / "duai" / "i18n"
        else:
            # duai/i18n.py -> duai/i18n/translations
            base = Path(__file__).parent / "i18n" / "translations"
        return base

    def _load_all_translations(self):
        """Carga todos los .json del directorio translations."""
        trans_dir = self._get_translations_dir()
        if not trans_dir.exists():
            self._load_embedded_fallback()
            return

        for json_file in trans_dir.glob("*.json"):
            lang_code = json_file.stem
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    self._translations[lang_code] = json.load(f)
                # Construir cadena fallback: es-MX → es → en
                base_lang = lang_code.split("-")[0]
                self._fallback_chain[lang_code] = [lang_code, base_lang, "en"] if base_lang != "en" else [lang_code, "en"]
            except (json.JSONDecodeError, OSError) as e:
                print(f"[i18n] Error cargando {json_file}: {e}")

        # Asegurar inglés como fallback final
        if "en" not in self._translations:
            self._load_embedded_fallback()

        self._register_plural_rules()

    def _load_embedded_fallback(self):
        """Carga traducciones mínimas embebidas como último recurso."""
        self._translations["es"] = self._get_embedded_es()
        self._translations["en"] = self._get_embedded_en()
        self._fallback_chain["es"] = ["es", "en"]
        self._fallback_chain["en"] = ["en"]

    def _register_plural_rules(self):
        """Registra funciones de pluralización por idioma (reglas CLDR)."""
        self._plural_rules["es"] = lambda n: "plural" if n != 1 else "singular"
        self._plural_rules["en"] = lambda n: "plural" if n != 1 else "singular"
        self._plural_rules["fr"] = lambda n: "plural" if n > 1 else "singular"
        self._plural_rules["pl"] = lambda n: (
            "plural" if n == 1 else
            "few" if 2 <= (n % 10) <= 4 and (n % 100 < 10 or n % 100 >= 20) else
            "many"
        )
        self._plural_rules["default"] = lambda n: "plural" if n != 1 else "singular"

    def _get_embedded_es(self) -> Dict:
        return {
            "nav": {"resumen": "RESUMEN", "escaneo": "ESCANEO", "limpieza": "LIMPIEZA", "sesion": "SESIÓN", "panico": "PÁNICO", "ajustes": "AJUSTES", "terminal": "TERMINAL", "logros": "LOGROS", "actualizaciones": "ACTUALIZACIONES"},
            "app": {"title": "duAI", "theme_dark": "MODO OSCURO", "theme_light": "MODO CLARO"},
            "dash": {"status": "ESTADO", "hero": "Privacidad absoluta.", "traces": "RASTROS", "risk": "RIESGO", "freed": "LIBERADO", "last_scan": "ÚLT. ESCANEO", "never": "Nunca", "btn_scan": "ESCANEAR", "btn_clean": "LIMPIAR", "btn_quick": "LIMPIEZA RÁPIDA"},
            "scan": {"title": "ESCANEO DE PRIVACIDAD", "start": "INICIAR ESCANEO", "cancel": "CANCELAR", "done": "{found} rastros, {bytes} en {elapsed}s ({time})", "progress": "Escaneando {name}...", "empty": "Sin rastros de IA detectados.", "col_target": "Objetivo", "col_category": "Categoría", "col_status": "Estado", "col_items": "Items", "col_size": "Tamaño"},
            "clean": {"title": "LIMPIEZA SEGURA", "preview": "Vista previa", "recycle": "Papelera", "permanent": "Permanente", "quarantine": "Cuarentena", "run": "EJECUTAR LIMPIEZA", "select_all": "Seleccionar todo", "deselect_all": "Deseleccionar todo", "no_targets": "Sin objetivos seleccionados"},
            "panic": {"title": "MODO PÁNICO", "btn": "ACTIVAR PÁNICO", "confirm": "Esto eliminará TODOS los rastros. ¿Confirmar?", "running": "Ejecutando modo pánico...", "done": "Pánico completado.", "error": "Error en modo pánico: "},
            "settings": {"title": "CONFIGURACIÓN", "general": "GENERAL", "cleanup": "LIMPIEZA", "security": "SEGURIDAD", "appearance": "APARIENCIA", "gamification": "GAMIFICACIÓN", "language": "Idioma", "theme": "Tema", "accent": "Color de acento", "high_contrast": "Alto contraste", "follow_system": "Seguir tema del sistema", "exclusions": "Exclusiones", "password": "Contraseña", "hotkey": "Hotkey global", "updates": "Actualizaciones", "gamification_toggle": "Habilitar logros", "share_platform": "Plataforma compartir"},
            "session": {"title": "SESIÓN AISLADA", "new": "Nueva sesión", "running": "Ejecutando...", "stop": "Detener", "output": "Salida"},
            "terminal": {"title": "TERMINAL AISLADA", "prompt": "duAI>", "clear": "Limpiar", "copy": "Copiar"},
            "viral": {"title": "LOGROS Y SOCIAL", "stats": "ESTADÍSTICAS", "scans": "Escaneos", "cleans": "Limpiezas", "panics": "Pánicos", "freed": "Liberado", "streak": "RACHA", "achievements": "LOGROS DESBLOQUEADOS", "locked": "BLOQUEADOS", "share": "COMPARTIR", "copy_report": "COPIAR REPORTE", "save_png": "GUARDAR REPORTE PNG"},
            "updater": {"title": "ACTUALIZACIONES", "check": "VERIFICAR", "latest": "Última versión: {version}", "current": "Versión actual: {version}", "available": "¡Disponible: {version}!", "downloading": "Descargando...", "install": "INSTALAR", "notes": "Notas de la versión:"},
            "plural": {
                "items_found": {"singular": "{count} elemento encontrado", "plural": "{count} elementos encontrados"},
                "bytes_freed": {"singular": "{count} byte liberado", "plural": "{count} bytes liberados"},
                "days_streak": {"singular": "{count} día limpio", "plural": "{count} días limpios"},
            },
        }

    def _get_embedded_en(self) -> Dict:
        return {
            "nav": {"resumen": "DASHBOARD", "escaneo": "SCAN", "limpieza": "CLEAN", "sesion": "SESSION", "panico": "PANIC", "ajustes": "SETTINGS", "terminal": "TERMINAL", "logros": "ACHIEVEMENTS", "actualizaciones": "UPDATES"},
            "app": {"title": "duAI", "theme_dark": "DARK MODE", "theme_light": "LIGHT MODE"},
            "dash": {"status": "STATUS", "hero": "Absolute privacy.", "traces": "TRACES", "risk": "RISK", "freed": "FREED", "last_scan": "LAST SCAN", "never": "Never", "btn_scan": "SCAN", "btn_clean": "CLEAN", "btn_quick": "QUICK CLEAN"},
            "scan": {"title": "PRIVACY SCAN", "start": "START SCAN", "cancel": "CANCEL", "done": "{found} traces, {bytes} in {elapsed}s ({time})", "progress": "Scanning {name}...", "empty": "No AI traces detected.", "col_target": "Target", "col_category": "Category", "col_status": "Status", "col_items": "Items", "col_size": "Size"},
            "clean": {"title": "SAFE CLEANUP", "preview": "Preview", "recycle": "Recycle", "permanent": "Permanent", "quarantine": "Quarantine", "run": "RUN CLEANUP", "select_all": "Select All", "deselect_all": "Deselect All", "no_targets": "No targets selected"},
            "panic": {"title": "PANIC MODE", "btn": "ACTIVATE PANIC", "confirm": "This will delete ALL traces. Confirm?", "running": "Running panic mode...", "done": "Panic completed.", "error": "Panic mode error: "},
            "settings": {"title": "SETTINGS", "general": "GENERAL", "cleanup": "CLEANUP", "security": "SECURITY", "appearance": "APPEARANCE", "gamification": "GAMIFICATION", "language": "Language", "theme": "Theme", "accent": "Accent Color", "high_contrast": "High Contrast", "follow_system": "Follow System Theme", "exclusions": "Exclusions", "password": "Password", "hotkey": "Global Hotkey", "updates": "Updates", "gamification_toggle": "Enable Achievements", "share_platform": "Share Platform"},
            "session": {"title": "ISOLATED SESSION", "new": "New Session", "running": "Running...", "stop": "Stop", "output": "Output"},
            "terminal": {"title": "ISOLATED TERMINAL", "prompt": "duAI>", "clear": "Clear", "copy": "Copy"},
            "viral": {"title": "ACHIEVEMENTS & SOCIAL", "stats": "STATISTICS", "scans": "Scans", "cleans": "Cleans", "panics": "Panics", "freed": "Freed", "streak": "STREAK", "achievements": "UNLOCKED", "locked": "LOCKED", "share": "SHARE", "copy_report": "COPY REPORT", "save_png": "SAVE PNG REPORT"},
            "updater": {"title": "UPDATES", "check": "CHECK", "latest": "Latest version: {version}", "current": "Current version: {version}", "available": "Available: {version}!", "downloading": "Downloading...", "install": "INSTALL", "notes": "Release notes:"},
            "plural": {
                "items_found": {"singular": "{count} item found", "plural": "{count} items found"},
                "bytes_freed": {"singular": "{count} byte freed", "plural": "{count} bytes freed"},
                "days_streak": {"singular": "{count} day clean", "plural": "{count} days clean"},
            },
        }

    def set_language(self, lang: str) -> bool:
        """Establece idioma activo. Returns True si disponible."""
        lang = lang.lower()
        if lang in self._translations:
            self._current_lang = lang
            get_settings().set("language", lang)
            return True
        base = lang.split("-")[0]
        if base in self._translations:
            self._current_lang = base
            get_settings().set("language", base)
            return True
        return False

    def get_language(self) -> str:
        return self._current_lang

    def get_available_languages(self) -> List[Dict[str, str]]:
        native_names = {
            "es": "Español", "en": "English", "fr": "Français",
            "de": "Deutsch", "pt": "Português", "it": "Italiano",
            "ja": "日本語", "ko": "한국어", "zh": "中文", "ru": "Русский",
            "pl": "Polski", "nl": "Nederlands", "tr": "Türkçe",
        }
        return [
            {"code": code, "name": native_names.get(code, code.upper())}
            for code in sorted(self._translations.keys())
        ]

    def _resolve_key(self, lang: str, key: str) -> Optional[Union[str, dict]]:
        """Resuelve clave anidada (ej: 'nav.resumen') en diccionario idioma.

        Soporta dos formatos:
        - Anidado real: {"nav": {"resumen": "..."}}
        - Plana con punto: {"updater": {"step.download": "..."}}
        Tambien devuelve hojas tipo dict (para pluralizacion en tp()).
        """
        table = self._translations.get(lang, {})
        parts = key.split(".")
        for i, part in enumerate(parts):
            if not isinstance(table, dict):
                return None
            # Clave plana con punto (p. ej. "step.download") en este nivel
            remainder = ".".join(parts[i:])
            if remainder in table:
                return table[remainder]
            if part in table:
                table = table[part]
            else:
                return None
        return table if isinstance(table, (str, dict)) else None

    def t(self, key: str, **kwargs) -> str:
        """Traduce clave con interpolación. Soporta namespaces: 'nav.resumen'."""
        for lang in self._fallback_chain.get(self._current_lang, [self._current_lang, "en"]):
            text = self._resolve_key(lang, key)
            if isinstance(text, str):
                try:
                    return text.format(**kwargs) if kwargs else text
                except (KeyError, IndexError, ValueError):
                    # Placeholder no provisto: devolver el texto sin formatear
                    # en vez de romper la UI.
                    return text
        return key.format(**kwargs) if kwargs else key

    def tp(self, key: str, count: int, **kwargs) -> str:
        """Traduce con pluralización. Clave debe tener variantes 'singular'/'plural'."""
        kwargs["count"] = count
        rule = self._plural_rules.get(self._current_lang, self._plural_rules["default"])
        form = rule(count)

        for lang in self._fallback_chain.get(self._current_lang, [self._current_lang, "en"]):
            table = self._translations.get(lang, {})
            plural_table = self._resolve_key(lang, key)
            if isinstance(plural_table, dict):
                text = plural_table.get(form) or plural_table.get("plural") or plural_table.get("singular")
                if text:
                    return text.format(**kwargs) if kwargs else text

        return self.t(key, **kwargs)

    def tc(self, context: str, key: str, **kwargs) -> str:
        """Traduce con contexto/desambiguación: tc('button', 'save') → 'button.save'."""
        return self.t(f"{context}.{key}", **kwargs)

    def reload(self):
        """Recarga todas las traducciones desde disco."""
        self._translations.clear()
        self._fallback_chain.clear()
        self._load_all_translations()


# Backward compatibility
_manager = I18nManager()


def t(key: str, **kwargs) -> str:
    """Traduce clave al idioma actual. Soporta interpolación {name}."""
    return _manager.t(key, **kwargs)


def tp(key: str, count: int, **kwargs) -> str:
    """Traduce con soporte de pluralización."""
    return _manager.tp(key, count, **kwargs)


def tc(context: str, key: str, **kwargs) -> str:
    """Traduce con contexto para desambiguación."""
    return _manager.tc(context, key, **kwargs)


def set_language(lang: str) -> bool:
    """Establece idioma activo. Returns True si exitoso."""
    return _manager.set_language(lang)


def get_language() -> str:
    """Obtiene código de idioma activo."""
    return _manager.get_language()


def get_available_languages() -> List[Dict[str, str]]:
    """Obtiene lista de idiomas disponibles con nombres nativos."""
    return _manager.get_available_languages()


def reload_translations():
    """Recarga traducciones desde disco (desarrollo)."""
    _manager.reload()


def detect_system_language() -> str:
    """Detecta idioma del sistema para configuración inicial."""
    import locale
    try:
        lang, _ = locale.getdefaultlocale()
        if lang:
            lang = lang.lower()
            mapping = {
                "es_es": "es", "es_mx": "es", "es_ar": "es",
                "en_us": "en", "en_gb": "en", "en_ca": "en",
                "fr_fr": "fr", "fr_ca": "fr",
                "de_de": "de", "de_at": "de", "de_ch": "de",
                "pt_br": "pt", "pt_pt": "pt",
                "it_it": "it", "ja_jp": "ja", "ko_kr": "ko",
                "zh_cn": "zh", "zh_tw": "zh", "ru_ru": "ru",
                "pl_pl": "pl", "nl_nl": "nl", "tr_tr": "tr",
            }
            return mapping.get(lang, lang.split("_")[0])
    except Exception:
        pass
    return "en"