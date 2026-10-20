import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QProxyStyle, QStyleFactory

if getattr(sys, "frozen", False):
    THEME_DIR = os.path.join(sys._MEIPASS, "duai", "ui")
else:
    THEME_DIR = os.path.dirname(__file__)

# Unico tema: negro puro con letras blancas (no hay modo claro para evitar errores visuales)
PALETTES = {
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
# Nota: el acento default ("") usa el color de primer plano para que los botones sean visibles
ACCENT_COLORS = {
    "": {"ACCENT": "#FFFFFF", "ACCENT_HOVER": "#9A9A9A"},
    "red": {"ACCENT": "#FF0040", "ACCENT_HOVER": "#FF3366"},
    "green": {"ACCENT": "#00FF40", "ACCENT_HOVER": "#33FF66"},
    "blue": {"ACCENT": "#0066FF", "ACCENT_HOVER": "#3380FF"},
    "purple": {"ACCENT": "#CC00FF", "ACCENT_HOVER": "#E033FF"},
}

_current_mode = "oscuro"
_current_accent = ""


def current_mode():
    return _current_mode


def current_accent():
    return _current_accent


def color(key):
    base = PALETTES.get(_current_mode, PALETTES["oscuro"])
    if key in ("ACCENT", "ACCENT_HOVER"):
        return ACCENT_COLORS.get(_current_accent, ACCENT_COLORS[""]).get(key, base["FG"])
    return base.get(key, "#000000")


class DarkProxyStyle(QProxyStyle):
    """Estilo proxy que fuerza texto blanco en todos los widgets,
    evitando que el estilo nativo de Windows use texto negro sobre fondo negro."""
    def __init__(self, style=None):
        super().__init__(style or QStyleFactory.create("Fusion"))

    @staticmethod
    def _make_palette() -> QPalette:
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#000000"))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#0D0D0D"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#000000"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#1C1C1C"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        return pal

    def standardPalette(self) -> QPalette:
        return DarkProxyStyle._make_palette()


def render_css(mode=None, accent=None):
    global _current_mode, _current_accent
    if mode in PALETTES:
        _current_mode = mode
    if accent is not None:
        _current_accent = accent
    palette = PALETTES.get(_current_mode, PALETTES["oscuro"])
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

    # Forzar estilo Fusion con paleta oscura para que texto sea blanco
    app.setStyle(DarkProxyStyle())
    app.setPalette(DarkProxyStyle._make_palette())
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(render_css(_current_mode, _current_accent))
    return _current_mode, _current_accent
