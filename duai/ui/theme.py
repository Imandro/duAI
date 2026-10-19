import os
import sys

from PySide6.QtGui import QFont

if getattr(sys, "frozen", False):
    THEME_DIR = os.path.join(sys._MEIPASS, "duai", "ui")
else:
    THEME_DIR = os.path.dirname(__file__)

PALETTES = {
    "claro": {
        "BG": "#FFFFFF",
        "FG": "#000000",
        "SOFT": "#8A8A8A",
        "BODY": "#2A2A2A",
        "LINE": "#E0E0E0",
        "GRID": "#F0F0F0",
        "ALT": "#FAFAFA",
        "HOVER": "#F5F5F5",
        "HANDLE": "#2A2A2A",
    },
    "oscuro": {
        "BG": "#000000",
        "FG": "#FFFFFF",
        "SOFT": "#9A9A9A",
        "BODY": "#D6D6D6",
        "LINE": "#2E2E2E",
        "GRID": "#181818",
        "ALT": "#0D0D0D",
        "HOVER": "#1C1C1C",
        "HANDLE": "#CFCFCF",
    },
}

# Colores de acento opcional (para romper el monocromatico cuando el usuario lo desee)
ACCENT_COLORS = {
    "": {"ACCENT": "#000000", "ACCENT_HOVER": "#3A3A3A"},
    "red": {"ACCENT": "#FF0040", "ACCENT_HOVER": "#FF3366"},
    "green": {"ACCENT": "#00FF40", "ACCENT_HOVER": "#33FF66"},
    "blue": {"ACCENT": "#0066FF", "ACCENT_HOVER": "#3380FF"},
    "purple": {"ACCENT": "#CC00FF", "ACCENT_HOVER": "#E033FF"},
}

_current_mode = "claro"
_current_accent = ""


def current_mode():
    return _current_mode


def current_accent():
    return _current_accent


def color(key):
    base = PALETTES.get(_current_mode, PALETTES["claro"])
    if key in ("ACCENT", "ACCENT_HOVER"):
        return ACCENT_COLORS.get(_current_accent, ACCENT_COLORS[""]).get(key, base["FG"])
    return base.get(key, "#000000")


def render_css(mode=None, accent=None):
    global _current_mode, _current_accent
    if mode in PALETTES:
        _current_mode = mode
    if accent is not None:
        _current_accent = accent
    palette = PALETTES.get(_current_mode, PALETTES["claro"])
    accent_palette = ACCENT_COLORS.get(_current_accent, ACCENT_COLORS[""])
    qss_path = os.path.join(THEME_DIR, "theme.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as fh:
            template = fh.read()
    except FileNotFoundError:
        template = "* { background: __BG__; color: __FG__; font-family: 'Segoe UI'; font-size: 13px; }"
    css = template
    for key, value in palette.items():
        css = css.replace("__" + key + "__", value)
    for key, value in accent_palette.items():
        css = css.replace("__" + key + "__", value)
    return css


def apply_theme(app, mode=None, accent=None):
    global _current_mode, _current_accent
    if mode in PALETTES:
        _current_mode = mode
    if accent is not None:
        _current_accent = accent
    app.setStyleSheet(render_css(_current_mode, _current_accent))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    return _current_mode, _current_accent
