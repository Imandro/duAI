import os
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMenu, QPushButton, QVBoxLayout, QWidget

from ..utils.settings import get_settings


class PanicFloatWidget(QWidget):
    def __init__(self, main_window):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.mw = main_window
        self.setObjectName("floatFrame")
        self._size = get_settings().get("float_size") or 160
        self.setFixedSize(self._size, self._size)
        self._drag_offset = None
        self._moved = False
        self._last_click = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.button = QPushButton()
        self.button.setObjectName("floatPanicBtn")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFixedSize(self._size, self._size)
        self.button.clicked.connect(self._fire)

        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(__file__), "..", "..")
        icon_path = os.path.join(base, "assets", "panic_button.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled = pixmap.scaled(
                self._size, self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.button.setIcon(scaled)
            self.button.setIconSize(self.button.rect().size())

        layout.addWidget(self.button)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        settings = get_settings()
        x, y = settings.get("float_x"), settings.get("float_y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)

    def _fire(self):
        now = time.time()
        if now - self._last_click < 2.0:
            return
        if self._moved:
            return
        self._last_click = now
        self.mw.trigger_panic()

    def _menu(self, pos):
        menu = QMenu(self)
        open_action = menu.addAction("ABRIR duAI")
        hide_action = menu.addAction("OCULTAR WIDGET")
        quit_action = menu.addAction("SALIR de duAI")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is open_action:
            self.mw.showNormal()
            self.mw.activateWindow()
        elif chosen is hide_action:
            self.mw.hide_panic_float()
        elif chosen is quit_action:
            self.mw.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = (event.globalPosition().toPoint() - self.frameGeometry().topLeft())
            if (delta.x() ** 2 + delta.y() ** 2) > 25:
                self._moved = True
                self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            get_settings().set("float_x", self.x())
            get_settings().set("float_y", self.y())
        super().mouseReleaseEvent(event)
