from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
