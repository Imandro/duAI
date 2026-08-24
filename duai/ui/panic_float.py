import time

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QMenu, QWidget

from ..i18n import t
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
        self._size = get_settings().get("float_size") or 160
        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._dragging = False
        self._drag_start = QPoint()
        self._moved = False
        self._press_pos = QPoint()
        self._hover = False
        self._click_time = 0.0

        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        settings = get_settings()
        x, y = settings.get("float_x"), settings.get("float_y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)

    def paintEvent(self, event):
        s = min(self.width(), self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 30, 30)))
        painter.drawEllipse(0, 0, s, s)

        border = max(int(s * 0.04), 2)
        if self._hover:
            painter.setBrush(QBrush(QColor(210, 40, 40)))
        else:
            painter.setBrush(QBrush(QColor(190, 35, 35)))
        painter.drawEllipse(border, border, s - border * 2, s - border * 2)

        font_size = max(int(s * 0.25), 10)
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Segoe UI", font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "duAI")
        painter.end()

    def enterEvent(self, event):
        self._hover = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_start = event.globalPosition().toPoint() - self.pos()
            self._dragging = False
            self._moved = False
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            current = event.globalPosition().toPoint()
            if not self._dragging:
                if (current - self._press_pos).manhattanLength() > 5:
                    self._dragging = True
                    self._moved = True
            if self._dragging:
                self.move(current - self._drag_start)
                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._dragging = False
            self._drag_start = QPoint()
            if was_dragging:
                get_settings().set("float_x", self.x())
                get_settings().set("float_y", self.y())
                event.accept()
                return
            if self._moved:
                event.accept()
                return
            now = time.time()
            if now - self._click_time < 0.35:
                self._click_time = 0.0
                self.mw.close()
                event.accept()
                return
            self._click_time = now
            QTimer.singleShot(350, self._single_click)
            event.accept()

    def _single_click(self):
        if self._click_time == 0.0:
            return
        self._click_time = 0.0
        self.mw.trigger_panic()

    def _menu(self, pos):
        menu = QMenu(self)
        open_action = menu.addAction(t("float.open"))
        hide_action = menu.addAction(t("float.hide"))
        quit_action = menu.addAction(t("float.quit"))
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is open_action:
            self.mw.showNormal()
            self.mw.activateWindow()
        elif chosen is hide_action:
            self.mw.hide_panic_float()
        elif chosen is quit_action:
            self.mw.close()
