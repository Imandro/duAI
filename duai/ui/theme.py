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

_current_mode = "claro"


def current_mode():
    return _current_mode


def color(key):
    return PALETTES.get(_current_mode, PALETTES["claro"]).get(key, "#000000")


def render_css(mode):
    palette = PALETTES.get(mode, PALETTES["claro"])
    qss_path = os.path.join(THEME_DIR, "theme.qss")
    with open(qss_path, "r", encoding="utf-8") as fh:
        template = fh.read()
    css = template
    for key, value in palette.items():
        css = css.replace("__" + key + "__", value)
    return css


def apply_theme(app, mode=None):
    global _current_mode
    if mode in PALETTES:
        _current_mode = mode
    app.setStyleSheet(render_css(_current_mode))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    return _current_mode
