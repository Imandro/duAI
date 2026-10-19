from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Worker con cancelacion cooperativa y reporte de progreso.

    El job (funcion pasada) debe aceptar un parametro opcional `cancel_cb`
    (callable que devuelve True si se solicita cancelacion) y opcionalmente
    `progress_cb` (callable para reportar progreso).

    Senales:
        done(object)   - emitido con el resultado del job
        failed(str)    - emitido con el mensaje de excepcion
        cancelled()    - emitido si el job se cancela
        progress(int)  - emitido con porcentaje 0-100 si el job usa progress_cb
    """

    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._cancelled = False

    def cancel(self):
        """Solicita cancelacion cooperativa. El job debe revisar cancel_cb()."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        try:
            # Inyectar cancel_cb y progress_cb si el job los acepta
            import inspect

            sig = inspect.signature(self._fn)
            kwargs = {}
            if "cancel_cb" in sig.parameters:
                kwargs["cancel_cb"] = self.is_cancelled
            if "progress_cb" in sig.parameters:
                kwargs["progress_cb"] = self.progress.emit

            if kwargs:
                result = self._fn(**kwargs)
            else:
                result = self._fn()

            if self._cancelled:
                self.cancelled.emit()
            else:
                self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
