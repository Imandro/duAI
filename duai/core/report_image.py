"""Generador de imagen de reporte para compartir en redes.

Crea una imagen PNG con el resumen del escaneo: Privacy Score,
logros, stats, etc. Lista para compartir en Twitter, Telegram, etc.
"""

import os
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QColor, QPixmap, QBrush, QPen
from PySide6.QtWidgets import QApplication


def _ensure_app():
    """Garantiza que exista una QApplication/QGuiApplication.

    QPixmap requiere una QApplication; sin ella Qt aborta el proceso
    (crash 0xC0000409 en Windows).
    """
    if QApplication.instance() is None:
        return QApplication([])
    return QApplication.instance()


def _base_dir():
    from ..utils.logger import base_dir
    return base_dir()


def generate_report_image(score, found_count, freed_bytes, streak_days, achievements_unlocked, output_path=None):
    """Genera una imagen PNG con el reporte de privacidad.

    Args:
        score: Privacy Score (0-100)
        found_count: Rastros encontrados
        freed_bytes: Bytes liberados
        streak_days: Dias de racha
        achievements_unlocked: Numero de logros desbloqueados
        output_path: Ruta de salida (opcional)

    Returns:
        str: Ruta del archivo generado
    """
    if output_path is None:
        output_path = os.path.join(_base_dir(), "privacy_report.png")

    _ensure_app()

    width, height = 800, 500
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#000000"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fondo
    painter.fillRect(0, 0, width, height, QColor("#000000"))

    # Borde
    pen = QPen(QColor("#FFFFFF"), 2)
    painter.setPen(pen)
    painter.drawRect(1, 1, width - 2, height - 2)

    # Titulo
    font = QFont("Segoe UI", 24, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(QRect(0, 30, width, 40), Qt.AlignmentFlag.AlignCenter, "duAI — Privacy Report")

    # Subtitulo
    font = QFont("Segoe UI", 11)
    painter.setFont(font)
    painter.setPen(QColor("#9A9A9A"))
    painter.drawText(QRect(0, 75, width, 20), Qt.AlignmentFlag.AlignCenter, "Don't Use AI — 100% local, zero telemetry")

    # Privacy Score (grande, centrado)
    score_color = "#00FF40" if score >= 90 else ("#FFFFFF" if score >= 70 else ("#9A9A9A" if score >= 50 else "#FF0040"))
    font = QFont("Segoe UI", 72, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(score_color))
    painter.drawText(QRect(0, 110, width, 90), Qt.AlignmentFlag.AlignCenter, str(score))

    font = QFont("Segoe UI", 14)
    painter.setFont(font)
    painter.setPen(QColor("#9A9A9A"))
    painter.drawText(QRect(0, 200, width, 25), Qt.AlignmentFlag.AlignCenter, "Privacy Score / 100")

    # Stats grid
    y = 250
    stats = [
        ("Rastros encontrados", str(found_count)),
        ("Bytes liberados", _fmt_bytes(freed_bytes)),
        ("Racha de privacidad", f"{streak_days} dias"),
        ("Logros desbloqueados", str(achievements_unlocked)),
    ]

    font = QFont("Segoe UI", 11)
    painter.setFont(font)
    for i, (label, value) in enumerate(stats):
        x = 60 + (i % 2) * 380
        row_y = y + (i // 2) * 60

        # Label
        painter.setPen(QColor("#9A9A9A"))
        painter.drawText(QRect(x, row_y, 180, 20), Qt.AlignmentFlag.AlignLeft, label)

        # Value
        font_v = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font_v)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRect(x, row_y + 20, 180, 25), Qt.AlignmentFlag.AlignLeft, value)
        painter.setFont(font)

    # Footer
    font = QFont("Segoe UI", 9)
    painter.setFont(font)
    painter.setPen(QColor("#888888"))
    painter.drawText(QRect(0, height - 40, width, 20), Qt.AlignmentFlag.AlignCenter,
                     f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} — github.com/Imandro/duAI")

    painter.end()

    pixmap.save(output_path, "PNG")
    return output_path


def _fmt_bytes(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def generate_and_open(score, found_count, freed_bytes, streak_days, achievements_unlocked,
                      open_file=True):
    """Genera la imagen y (opcionalmente) la abre con el visor por defecto."""
    path = generate_report_image(score, found_count, freed_bytes, streak_days, achievements_unlocked)
    if not open_file or os.environ.get("DUAI_NO_OPEN"):
        return path
    try:
        import subprocess
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception:
        pass
    return path
