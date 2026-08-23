import os
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer

app = QApplication(sys.argv)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
sizes = [16, 32, 48, 64, 128, 256]

for svg_name, prefix in [("duAI_black.svg", "duAI"), ("duAI_white.svg", "duAI_white")]:
    svg_path = os.path.join(ASSETS, svg_name)
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print(f"SVG INVALIDO: {svg_path}")
        continue

    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        out = os.path.join(ASSETS, f"{prefix}_{size}.png")
        image.save(out, "PNG")

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    main = os.path.join(ASSETS, f"{prefix}.png")
    image.save(main, "PNG")
    print(f"{prefix}.png: {os.path.getsize(main)} bytes")

from PIL import Image as PILImage

ico_path = os.path.join(ASSETS, "duAI.ico")
imgs = [PILImage.open(os.path.join(ASSETS, f"duAI_{s}.png")) for s in sizes]
imgs[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
print(f"ICO: {os.path.getsize(ico_path)} bytes")
