import os
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, QSize
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

    svg_size = renderer.defaultSize()
    svg_w = svg_size.width()
    svg_h = svg_size.height()

    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scale = min(size / svg_w, size / svg_h)
        scaled_w = svg_w * scale
        scaled_h = svg_h * scale
        x = (size - scaled_w) / 2
        y = (size - scaled_h) / 2

        renderer.render(painter, QRectF(x, y, scaled_w, scaled_h))
        painter.end()
        out = os.path.join(ASSETS, f"{prefix}_{size}.png")
        image.save(out, "PNG")

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    scale = min(256 / svg_w, 256 / svg_h)
    scaled_w = svg_w * scale
    scaled_h = svg_h * scale
    x = (256 - scaled_w) / 2
    y = (256 - scaled_h) / 2

    renderer.render(painter, QRectF(x, y, scaled_w, scaled_h))
    painter.end()
    main = os.path.join(ASSETS, f"{prefix}.png")
    image.save(main, "PNG")
    print(f"{prefix}.png: {os.path.getsize(main)} bytes")

from PIL import Image as PILImage

ico_path = os.path.join(ASSETS, "duAI.ico")
imgs = [PILImage.open(os.path.join(ASSETS, f"duAI_{s}.png")) for s in sizes]
imgs[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
print(f"ICO: {os.path.getsize(ico_path)} bytes")
