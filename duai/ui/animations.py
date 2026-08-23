from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QVariantAnimation,
    Qt,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QStackedWidget,
    QWidget,
)

FAST = 160
NORMAL = 240
SLOW = 380


def _keep(widget, name, anim):
    widget.__dict__[name] = anim
    return anim


def fade_widget(widget: QWidget, duration=NORMAL, start=0.0, end=1.0, cleanup=False):
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _finish():
        if cleanup:
            widget.setGraphicsEffect(None)

    anim.finished.connect(_finish)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return _keep(widget, "_fade_anim", anim)


class FadeStack(QStackedWidget):
    def setCurrentIndexAnimated(self, index):
        if index == self.currentIndex():
            self.setCurrentIndex(index)
            return
        self.setCurrentIndex(index)
        page = self.widget(index)
        fade_widget(page, duration=200, start=0.0, end=1.0, cleanup=True)

    def setCurrentIndex(self, index):  # compat: siempre animado
        super().setCurrentIndex(index)


def fade_window(window, duration=SLOW, end=1.0):
    anim = QPropertyAnimation(window, b"windowOpacity", window)
    anim.setDuration(duration)
    anim.setStartValue(window.windowOpacity())
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutQuad)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return _keep(window, "_win_fade", anim)


def theme_dip(window, duration=300, low=0.55, on_mid=None, on_done=None):
    anim = QVariantAnimation(window)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _tick(t):
        t = float(t)
        window.setWindowOpacity(1.0 - (1.0 - low) * (t if t < 0.5 else 1.0 - t))

    def _mid():
        if on_mid:
            on_mid()

    def _end():
        window.setWindowOpacity(1.0)
        if on_done:
            on_done()

    anim.valueChanged.connect(_tick)
    anim.finished.connect(_end)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(int(duration / 2), _mid)
    anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return _keep(window, "_theme_dip", anim)


def animate_max_height(widget: QWidget, start: int, end: int, duration=NORMAL, on_done=None):
    widget.setMaximumHeight(max(0, start))
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(max(0, start))
    anim.setEndValue(max(0, end))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _finish():
        if on_done:
            on_done()

    anim.finished.connect(_finish)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return _keep(widget, "_height_anim", anim)


def count_to(label, value: int, formatter=str, duration=550):
    previous = getattr(label, "_count_val", 0)
    anim = QVariantAnimation(label)
    anim.setDuration(duration)
    anim.setStartValue(previous)
    anim.setEndValue(value)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _tick(v):
        iv = int(round(float(v)))
        label._count_val = iv
        label.setText(formatter(iv))

    anim.valueChanged.connect(_tick)
    anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return _keep(label, "_count_anim", anim)


class Pulsing:
    def __init__(self, widget: QWidget, low=0.62, duration=1500):
        self.widget = widget
        self.low = low
        self.duration = duration
        self.effect = None
        self.anim = None

    def start(self):
        if self.anim is not None:
            return
        self.effect = QGraphicsOpacityEffect(self.widget)
        self.effect.setOpacity(1.0)
        self.widget.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self.widget)
        self.anim.setDuration(self.duration)
        self.anim.setStartValue(1.0)
        self.anim.setKeyValueAt(0.5, self.low)
        self.anim.setEndValue(1.0)
        self.anim.setLoopCount(-1)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.anim.start()

    def stop(self):
        if self.anim is None:
            return
        self.anim.stop()
        self.anim = None
        self.widget.setGraphicsEffect(None)
