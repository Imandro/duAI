"""Sistema de temas para duAI - Múltiples temas, acentos, alto contraste, detección de sistema."""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QProxyStyle, QStyleFactory, QApplication


if getattr(sys, "frozen", False):
    THEME_DIR = os.path.join(sys._MEIPASS, "duai", "ui")
else:
    THEME_DIR = os.path.dirname(__file__)


@dataclass
class ColorPalette:
    """Tokens semánticos de color para tematización consistente."""
    # Superficies base
    bg_primary: str = "#000000"
    bg_secondary: str = "#0D0D0D"
    bg_tertiary: str = "#181818"
    bg_hover: str = "#1C1C1C"
    bg_active: str = "#2E2E2E"

    # Texto
    fg_primary: str = "#FFFFFF"
    fg_secondary: str = "#D6D6D6"
    fg_muted: str = "#9A9A9A"
    fg_disabled: str = "#555555"

    # Bordes
    border_subtle: str = "#181818"
    border_default: str = "#2E2E2E"
    border_focus: str = "#FFFFFF"

    # Semánticos
    accent: str = "#FFFFFF"
    accent_hover: str = "#9A9A9A"
    accent_text: str = "#000000"

    success: str = "#FFFFFF"
    success_hover: str = "#FFFFFF"
    warning: str = "#FFB800"
    warning_hover: str = "#FFCC33"
    error: str = "#FF0040"
    error_hover: str = "#FF3366"

    # Interactivos
    handle: str = "#CFCFCF"
    overlay: str = "rgba(0, 0, 0, 0.8)"


@dataclass
class Theme:
    """Definición completa de tema."""
    name: str
    display_name: str
    palette: ColorPalette
    is_high_contrast: bool = False
    is_dark: bool = True
    font_family: str = "Segoe UI"
    font_size_base: int = 13
    border_radius: int = 4


# ============================================================
# TEMAS INTEGRADOS
# ============================================================

DARK_PALETTE = ColorPalette(
    bg_primary="#000000",
    bg_secondary="#0D0D0D",
    bg_tertiary="#181818",
    bg_hover="#1C1C1C",
    bg_active="#2E2E2E",
    fg_primary="#FFFFFF",
    fg_secondary="#D6D6D6",
    fg_muted="#9A9A9A",
    fg_disabled="#555555",
    border_subtle="#181818",
    border_default="#2E2E2E",
    border_focus="#FFFFFF",
    accent="#FFFFFF",
    accent_hover="#9A9A9A",
    accent_text="#000000",
    success="#FFFFFF",
    success_hover="#FFFFFF",
    warning="#FFB800",
    warning_hover="#FFCC33",
    error="#FF0040",
    error_hover="#FF3366",
    handle="#CFCFCF",
)

DARK_HIGH_CONTRAST_PALETTE = ColorPalette(
    bg_primary="#000000",
    bg_secondary="#000000",
    bg_tertiary="#111111",
    bg_hover="#222222",
    bg_active="#333333",
    fg_primary="#FFFFFF",
    fg_secondary="#FFFFFF",
    fg_muted="#CCCCCC",
    fg_disabled="#888888",
    border_subtle="#444444",
    border_default="#FFFFFF",
    border_focus="#FFFF00",
    accent="#FFFF00",
    accent_hover="#FFFF33",
    accent_text="#000000",
    success="#FFFFFF",
    success_hover="#FFFFFF",
    warning="#FFFF00",
    warning_hover="#FFFF33",
    error="#FF0000",
    error_hover="#FF3333",
    handle="#FFFFFF",
)

LIGHT_PALETTE = ColorPalette(
    bg_primary="#FFFFFF",
    bg_secondary="#F5F5F5",
    bg_tertiary="#EEEEEE",
    bg_hover="#E0E0E0",
    bg_active="#D0D0D0",
    fg_primary="#000000",
    fg_secondary="#333333",
    fg_muted="#666666",
    fg_disabled="#999999",
    border_subtle="#DDDDDD",
    border_default="#CCCCCC",
    border_focus="#0066FF",
    accent="#0066FF",
    accent_hover="#3380FF",
    accent_text="#FFFFFF",
    success="#008000",
    success_hover="#33AA33",
    warning="#CC8800",
    warning_hover="#DD9900",
    error="#CC0000",
    error_hover="#FF3333",
    handle="#666666",
)

LIGHT_HIGH_CONTRAST_PALETTE = ColorPalette(
    bg_primary="#FFFFFF",
    bg_secondary="#FFFFFF",
    bg_tertiary="#EEEEEE",
    bg_hover="#DDDDDD",
    bg_active="#CCCCCC",
    fg_primary="#000000",
    fg_secondary="#000000",
    fg_muted="#333333",
    fg_disabled="#666666",
    border_subtle="#BBBBBB",
    border_default="#000000",
    border_focus="#0000FF",
    accent="#0000FF",
    accent_hover="#3333FF",
    accent_text="#FFFFFF",
    success="#006600",
    success_hover="#008800",
    warning="#996600",
    warning_hover="#BB8800",
    error="#CC0000",
    error_hover="#EE0000",
    handle="#000000",
)


# ============================================================
# PRESETS DE ACENTO (se aplican sobre el tema)
# ============================================================

ACCENT_PRESETS = {
    "": {"name": "Monocromo", "accent": "#FFFFFF", "accent_hover": "#9A9A9A", "accent_text": "#000000"},
    "red": {"name": "Neon Red", "accent": "#FF0040", "accent_hover": "#FF3366", "accent_text": "#FFFFFF"},
    "green": {"name": "Neon Green", "accent": "#00FF40", "accent_hover": "#33FF66", "accent_text": "#000000"},
    "blue": {"name": "Neon Blue", "accent": "#0066FF", "accent_hover": "#3380FF", "accent_text": "#FFFFFF"},
    "purple": {"name": "Neon Purple", "accent": "#CC00FF", "accent_hover": "#E033FF", "accent_text": "#FFFFFF"},
    "orange": {"name": "Neon Orange", "accent": "#FF8800", "accent_hover": "#FFAA33", "accent_text": "#000000"},
    "cyan": {"name": "Neon Cyan", "accent": "#00FFFF", "accent_hover": "#33FFFF", "accent_text": "#000000"},
    "pink": {"name": "Neon Pink", "accent": "#FF00AA", "accent_hover": "#FF33CC", "accent_text": "#FFFFFF"},
}

THEMES: Dict[str, Theme] = {
    "dark": Theme("dark", "Oscuro", DARK_PALETTE, is_dark=True),
    "dark_hc": Theme("dark_hc", "Oscuro (Alto Contraste)", DARK_HIGH_CONTRAST_PALETTE, is_dark=True, is_high_contrast=True),
    "light": Theme("light", "Claro", LIGHT_PALETTE, is_dark=False),
    "light_hc": Theme("light_hc", "Claro (Alto Contraste)", LIGHT_HIGH_CONTRAST_PALETTE, is_dark=False, is_high_contrast=True),
}

_current_theme_id = "dark"
_current_accent_id = ""


# ============================================================
# PROXY STYLE
# ============================================================

class ThemeProxyStyle(QProxyStyle):
    """Proxy style que fuerza la paleta del tema."""
    def __init__(self, theme: Theme):
        super().__init__(QStyleFactory.create("Fusion"))
        self._theme = theme

    def standardPalette(self) -> QPalette:
        pal = QPalette()
        p = self._theme.palette
        pal.setColor(QPalette.ColorRole.Window, QColor(p.bg_primary))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(p.fg_primary))
        pal.setColor(QPalette.ColorRole.Base, QColor(p.bg_primary))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p.bg_secondary))
        pal.setColor(QPalette.ColorRole.Text, QColor(p.fg_primary))
        pal.setColor(QPalette.ColorRole.Button, QColor(p.bg_primary))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(p.fg_primary))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(p.accent))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p.accent_text))
        pal.setColor(QPalette.ColorRole.Link, QColor(p.accent))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.bg_tertiary))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p.fg_primary))
        return pal


# ============================================================
# GENERACIÓN CSS
# ============================================================

def _load_css_template() -> str:
    """Carga plantilla QSS desde archivo."""
    qss_path = os.path.join(THEME_DIR, "theme.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return _DEFAULT_CSS_TEMPLATE


_DEFAULT_CSS_TEMPLATE = """
* {
    background: __BG__;
    color: __FG__;
    font-family: "__FONT_FAMILY__";
    font-size: __FONT_SIZE__px;
    outline: none;
}
QMainWindow, QDialog { background: __BG__; }
#sidebar { background: __BG__; border-right: 1px solid __LINE__; }
QPushButton {
    background: __ACCENT__;
    color: __ACCENT_TEXT__;
    border: 1px solid __ACCENT__;
    border-radius: __BORDER_RADIUS__px;
    padding: 10px 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
}
QPushButton:hover { background: __ACCENT_HOVER__; border-color: __ACCENT_HOVER__; }
QPushButton:pressed { background: __BG__; color: __FG__; }
QPushButton:disabled { border-color: __BORDER_SUBTLE__; color: __FG__; background: __BG__; }
QLineEdit, QSpinBox, QComboBox {
    border: 1px solid __BORDER__;
    border-radius: __BORDER_RADIUS__px;
    padding: 8px 12px;
    background: __BG__;
    color: __FG__;
}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    border: 1px solid __BORDER__;
    background: __BG__;
    color: __FG__;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid __BORDER_FOCUS__; }
QTableWidget {
    border: 1px solid __BORDER__;
    gridline-color: transparent;
    selection-background-color: __HOVER__;
    selection-color: __FG__;
    alternate-background-color: __BG_SECONDARY__;
    background: __BG__;
    color: __FG__;
}
QTableView, QTreeView {
    border: 1px solid __BORDER__;
    gridline-color: transparent;
    selection-background-color: __HOVER__;
    selection-color: __FG__;
    alternate-background-color: __BG_SECONDARY__;
    background: __BG__;
    color: __FG__;
}
QTableView::item, QTreeView::item {
    padding: 6px 8px;
    border-bottom: 1px solid __BORDER__;
    color: __FG__;
}
QTableView::item:selected, QTreeView::item:selected {
    background: __HOVER__;
    color: __FG__;
}
QTableView:disabled, QTreeView:disabled { color: __FG__; background: __BG__; }
QHeaderView::section {
    background: __BG__;
    border: none;
    border-bottom: 2px solid __FG__;
    padding: 10px 8px;
    color: __SOFT__;
}
QCheckBox:disabled, QRadioButton:disabled { color: __FG__; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px; height: 18px;
    border: 2px solid __BORDER__;
    border-radius: __BORDER_RADIUS__px;
    background: __BG__;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: __ACCENT__;
    border-color: __ACCENT__;
}
QTextEdit {
    border: 1px solid __BORDER__;
    border-radius: __BORDER_RADIUS__px;
    font-family: "Consolas";
    font-size: 11px;
    color: __FG__;
    background: __BG__;
}
QScrollBar:vertical { background: __BG__; width: 6px; }
QScrollBar::handle:vertical { background: __HANDLE__; min-height: 30px; border-radius: 3px; }
#progressBar { background: __BORDER_SUBTLE__; border-radius: 2px; max-height: 4px; }
#progressBar::chunk { background: __ACCENT__; border-radius: 2px; }
QProgressBar {
    border: none;
    border-radius: 2px;
    background: __BG__;
    color: __FG__;
    text-align: center;
}
QProgressBar::chunk {
    background: __ACCENT__;
    border-radius: 2px;
}
#accentBtn { background: __ACCENT__; color: __ACCENT_TEXT__; }
#accentBtn:hover { background: __ACCENT_HOVER__; }
.status-success { color: __SUCCESS__; }
.status-warning { color: __WARNING__; }
.status-error { color: __ERROR__; }
"""


def _generate_css(theme: Theme, accent: Dict[str, str]) -> str:
    """Genera QSS combinando paleta del tema + acento (sustitucion por tokens __TOKEN__)."""
    p = theme.palette
    accent_final = accent.get("accent", p.accent)
    accent_hover_final = accent.get("accent_hover", p.accent_hover)
    accent_text_final = accent.get("accent_text", p.accent_text)

    tokens = {
        "__BG__": p.bg_primary,
        "__BG_SECONDARY__": p.bg_secondary,
        "__BG_TERTIARY__": p.bg_tertiary,
        "__HOVER__": p.bg_hover,
        "__ACTIVE__": p.bg_active,
        "__FG__": p.fg_primary,
        "__FG_SECONDARY__": p.fg_secondary,
        "__SOFT__": p.fg_muted,
        "__BODY__": p.fg_secondary,
        "__MUTED__": p.fg_muted,
        "__DISABLED__": p.fg_disabled,
        "__BORDER__": p.border_default,
        "__LINE__": p.border_default,
        "__BORDER_SUBTLE__": p.border_subtle,
        "__BORDER_FOCUS__": p.border_focus,
        "__GRID__": p.border_subtle,
        "__ALT__": p.bg_secondary,
        "__HANDLE__": p.handle,
        "__ACCENT__": accent_final,
        "__ACCENT_HOVER__": accent_hover_final,
        "__ACCENT_TEXT__": accent_text_final,
        "__SUCCESS__": p.success,
        "__SUCCESS_HOVER__": p.success_hover,
        "__WARNING__": p.warning,
        "__WARNING_HOVER__": p.warning_hover,
        "__ERROR__": p.error,
        "__ERROR_HOVER__": p.error_hover,
        "__FONT_FAMILY__": theme.font_family,
        "__FONT_SIZE__": str(theme.font_size_base),
        "__BORDER_RADIUS__": str(theme.border_radius),
    }

    css = _load_css_template()
    for token, value in tokens.items():
        css = css.replace(token, value)
    return css


# ============================================================
# API PÚBLICA
# ============================================================

def get_theme(theme_id: str) -> Optional[Theme]:
    return THEMES.get(theme_id)


def get_available_themes() -> List[Dict[str, str]]:
    return [
        {"id": tid, "name": t.display_name, "high_contrast": t.is_high_contrast}
        for tid, t in THEMES.items()
    ]


def get_available_accents() -> List[Dict[str, str]]:
    return [
        {"id": aid, "name": data["name"]}
        for aid, data in ACCENT_PRESETS.items()
    ]


# Alias con formato dict para uso directo en la UI de ajustes
AVAILABLE_THEMES: Dict[str, str] = {tid: t.display_name for tid, t in THEMES.items()}
AVAILABLE_ACCENTS: Dict[str, str] = {
    aid: data["name"] for aid, data in ACCENT_PRESETS.items() if aid
}

# Alias legaces y variantes (p. ej. "oscuro" -> "dark")
THEME_ALIASES: Dict[str, str] = {
    "oscuro": "dark", "dark": "dark", "negro": "dark",
    "claro": "light", "light": "light", "blanco": "light",
    "oscuro_hc": "dark_hc", "dark_hc": "dark_hc", "alto_contraste": "dark_hc",
    "claro_hc": "light_hc", "light_hc": "light_hc",
    "oscuro_alto_contraste": "dark_hc", "claro_alto_contraste": "light_hc",
}


def normalize_theme_id(value) -> Optional[str]:
    """Normaliza un ID/alias de tema a un ID valido de THEMES."""
    if not value:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip().lower().replace(" ", "_").replace("-", "_")
    if v in THEMES:
        return v
    return THEME_ALIASES.get(v)


def current_mode() -> str:
    """Devuelve el ID del tema actualmente aplicado."""
    return _current_theme_id


def current_theme_id() -> str:
    return _current_theme_id


def current_accent_id() -> str:
    return _current_accent_id


def current_theme() -> Theme:
    return THEMES[_current_theme_id]


def color(key: str) -> str:
    """Obtiene un color semántico del tema actual + acento."""
    theme = current_theme()
    p = theme.palette
    accent = ACCENT_PRESETS.get(_current_accent_id, ACCENT_PRESETS[""])

    mapping = {
        "BG": p.bg_primary,
        "BG_SECONDARY": p.bg_secondary,
        "BG_TERTIARY": p.bg_tertiary,
        "BG_HOVER": p.bg_hover,
        "FG": p.fg_primary,
        "FG_SECONDARY": p.fg_secondary,
        "SOFT": p.fg_muted,
        "MUTED": p.fg_muted,
        "DISABLED": p.fg_disabled,
        "LINE": p.border_default,
        "BORDER": p.border_default,
        "BORDER_SUBTLE": p.border_subtle,
        "BORDER_FOCUS": p.border_focus,
        "GRID": p.border_subtle,
        "ALT": p.bg_secondary,
        "HOVER": p.bg_hover,
        "HANDLE": p.handle,
        "ACCENT": accent["accent"],
        "ACCENT_HOVER": accent["accent_hover"],
        "ACCENT_TEXT": accent["accent_text"],
        "SUCCESS": p.success,
        "SUCCESS_HOVER": p.success_hover,
        "WARNING": p.warning,
        "WARNING_HOVER": p.warning_hover,
        "ERROR": p.error,
        "ERROR_HOVER": p.error_hover,
    }
    return mapping.get(key.upper(), p.fg_primary)


def render_css(theme_id: Optional[str] = None, accent_id: Optional[str] = None) -> str:
    global _current_theme_id, _current_accent_id
    theme_id = normalize_theme_id(theme_id) or theme_id
    if theme_id and theme_id in THEMES:
        _current_theme_id = theme_id
    if accent_id is not None and accent_id in ACCENT_PRESETS:
        _current_accent_id = accent_id

    theme = THEMES[_current_theme_id]
    accent = ACCENT_PRESETS.get(_current_accent_id, ACCENT_PRESETS[""])
    return _generate_css(theme, accent)


def apply_theme(app: QApplication, theme_id: Optional[str] = None, accent_id: Optional[str] = None) -> tuple:
    global _current_theme_id, _current_accent_id
    theme_id = normalize_theme_id(theme_id) or theme_id
    if theme_id and theme_id in THEMES:
        _current_theme_id = theme_id
    if accent_id is not None and accent_id in ACCENT_PRESETS:
        _current_accent_id = accent_id

    theme = THEMES[_current_theme_id]
    accent = ACCENT_PRESETS.get(_current_accent_id, ACCENT_PRESETS[""])

    # Aplicar estilo Fusion con paleta del tema
    app.setStyle(ThemeProxyStyle(theme))
    app.setPalette(ThemeProxyStyle(theme).standardPalette())
    app.setFont(QFont(theme.font_family, 10))
    app.setStyleSheet(render_css(_current_theme_id, _current_accent_id))

    # Persistir
    from ..utils.settings import get_settings
    get_settings().set("ui_mode", _current_theme_id)
    get_settings().set("accent_color", _current_accent_id)

    return _current_theme_id, _current_accent_id


def detect_system_theme() -> str:
    """Detecta preferencia de tema del sistema (Windows/macOS/Linux)."""
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        elif sys.platform == "darwin":
            import subprocess
            result = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
            return "dark" if "Dark" in result.stdout else "light"
        else:
            import subprocess
            result = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True)
            if "dark" in result.stdout.lower():
                return "dark"
            result = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True)
            if "dark" in result.stdout.lower():
                return "dark"
    except Exception:
        pass
    return "dark"


def get_effective_theme(prefer_system: bool = True) -> str:
    """Obtiene ID de tema respetando configuración usuario o preferencia sistema."""
    from ..utils.settings import get_settings
    settings = get_settings()

    # Verificar preferencia explícita del usuario
    ui_mode = settings.get("ui_mode")
    if ui_mode and normalize_theme_id(ui_mode) in THEMES:
        return normalize_theme_id(ui_mode)

    # Auto-detectar tema del sistema
    if prefer_system:
        system = detect_system_theme()
        hc = settings.get("high_contrast", False)
        return f"{system}_hc" if hc and f"{system}_hc" in THEMES else system

    return "dark"


def toggle_high_contrast(app: QApplication, enabled: bool) -> str:
    """Alterna variante alto contraste del tema actual."""
    current = _current_theme_id
    base = current.replace("_hc", "")
    new_theme = f"{base}_hc" if enabled else base

    if new_theme not in THEMES:
        new_theme = "dark_hc" if enabled else "dark"

    return apply_theme(app, new_theme, _current_accent_id)[0]