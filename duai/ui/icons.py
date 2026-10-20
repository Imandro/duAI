"""Iconos monocromaticos para duAI (sin emojis).

Todos los iconos se dibujan con QPainter en blanco sobre fondo negro,
consistentes con el tema monocromatico de la aplicacion.
"""

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont


def _make_icon(draw_func, size=24):
    """Crea un QIcon dibujando con la funcion draw_func."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_func(painter, size)
    painter.end()
    return QIcon(pixmap)


def _draw_trophy(painter, size):
    """Trofeo (logro desbloqueado)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Copa
    painter.drawEllipse(size // 4, 2, size // 2, size // 3)
    # Base
    painter.drawRect(size // 3, size * 2 // 3, size // 3, size // 6)
    painter.drawRect(size // 4, size * 5 // 6, size // 2, size // 8)


def _draw_skull(painter, size):
    """Calavera (sin racha)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Cabeza
    painter.drawEllipse(2, 2, size - 4, size * 2 // 3)
    # Ojos
    painter.setBrush(QBrush(QColor("#000000")))
    painter.drawEllipse(size // 4, size // 4, size // 6, size // 6)
    painter.drawEllipse(size * 2 // 3 - size // 6, size // 4, size // 6, size // 6)
    # Boca
    painter.setPen(QPen(QColor("#000000"), 2))
    painter.drawLine(size // 3, size * 2 // 3 - 2, size * 2 // 3, size * 2 // 3 - 2)


def _draw_seedling(painter, size):
    """Semilla (inicio de racha)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    # Tallo
    painter.drawLine(size // 2, size * 2 // 3, size // 2, size // 3)
    # Hoja izquierda
    painter.drawArc(size // 4, size // 4, size // 3, size // 3, 0, 180 * 16)
    # Hoja derecha
    painter.drawArc(size // 2, size // 4, size // 3, size // 3, 0, 180 * 16)
    # Suelo
    painter.drawLine(size // 4, size * 2 // 3, size * 3 // 4, size * 2 // 3)


def _draw_fire(painter, size):
    """Fuego (racha activa)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Llama principal
    painter.drawEllipse(size // 3, size // 4, size // 3, size // 2)
    # Llama secundaria
    painter.drawEllipse(size // 4, size // 2, size // 4, size // 3)
    painter.drawEllipse(size // 2, size // 2, size // 4, size // 3)


def _draw_lightning(painter, size):
    """Rayo (racha excelente)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Rayo zigzag
    points = [
        (size // 2, 2),
        (size // 3, size // 2),
        (size // 2, size // 2),
        (size // 3, size - 2),
    ]
    for i in range(len(points) - 1):
        painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])


def _draw_crown(painter, size):
    """Corona (racha legendaria)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Base
    painter.drawRect(size // 4, size * 2 // 3, size // 2, size // 6)
    # Picos
    painter.drawPolygon([
        (size // 4, size * 2 // 3),
        (size // 3, size // 3),
        (size // 2, size * 2 // 3),
        (size * 2 // 3, size // 3),
        (size * 3 // 4, size * 2 // 3),
    ])


def _draw_shield(painter, size):
    """Escudo (privacidad)."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Escudo
    painter.drawPolygon([
        (size // 2, 2),
        (size - 2, size // 3),
        (size - 2, size * 2 // 3),
        (size // 2, size - 2),
        (2, size * 2 // 3),
        (2, size // 3),
    ])


def _draw_check(painter, size):
    """Check (completado)."""
    pen = QPen(QColor("#FFFFFF"), 3)
    painter.setPen(pen)
    painter.drawLine(size // 4, size // 2, size // 2, size * 3 // 4)
    painter.drawLine(size // 2, size * 3 // 4, size * 3 // 4, size // 4)


def _draw_warning(painter, size):
    """Advertencia."""
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    # Triangulo
    painter.drawPolygon([
        (size // 2, 2),
        (size - 2, size - 2),
        (2, size - 2),
    ])
    # Exclamacion
    painter.setPen(QPen(QColor("#000000"), 2))
    painter.drawLine(size // 2, size // 3, size // 2, size * 2 // 3)
    painter.drawPoint(size // 2, size * 5 // 6)


# Iconos disponibles
TROPHY = _make_icon(_draw_trophy)
SKULL = _make_icon(_draw_skull)
SEEDLING = _make_icon(_draw_seedling)
FIRE = _make_icon(_draw_fire)
LIGHTNING = _make_icon(_draw_lightning)
CROWN = _make_icon(_draw_crown)
SHIELD = _make_icon(_draw_shield)
CHECK = _make_icon(_draw_check)
WARNING = _make_icon(_draw_warning)


def get_streak_icon(current):
    """Devuelve el icono apropiado para la racha actual."""
    if current == 0:
        return SKULL
    if current < 7:
        return SEEDLING
    if current < 30:
        return FIRE
    if current < 90:
        return LIGHTNING
    return CROWN


def get_streak_text(current):
    """Devuelve texto descriptivo para la racha (sin emojis)."""
    if current == 0:
        return "Sin racha activa"
    if current == 1:
        return "1 dia limpio"
    if current < 7:
        return f"{current} dias limpios"
    if current < 30:
        return f"{current} dias - Racha semanal"
    if current < 90:
        return f"{current} dias - Racha mensual"
    return f"{current} dias - Racha legendaria"
