import subprocess
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _OutputReader(threading.Thread):
    def __init__(self, proc, callback):
        super().__init__(daemon=True)
        self.proc = proc
        self.callback = callback

    def run(self):
        try:
            for line in iter(self.proc.stdout.readline, ""):
                if not line:
                    break
                self.callback(line)
        except Exception:
            pass
        try:
            self.proc.wait(timeout=1)
        except Exception:
            pass
        self.callback(f"\n[Proceso finalizado — codigo {self.proc.returncode}]\n")


class TerminalView(QWidget):
    command_run = Signal(str)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._process = None
        self._history = []
        self._history_index = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(12)

        header = QLabel("TERMINAL DEL SISTEMA")
        header.setObjectName("microLabel")
        layout.addWidget(header)

        title = QLabel("Consola")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Ejecuta comandos del sistema directamente. "
            "Los comandos se procesan en segundo plano."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        hint.setMaximumWidth(560)
        layout.addWidget(hint)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("terminalOutput")
        layout.addWidget(self.output, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        prompt = QLabel(">")
        prompt.setObjectName("promptMark")
        self.input = QLineEdit()
        self.input.setObjectName("terminalInput")
        self.input.setPlaceholderText("Escribe un comando...")
        self.input.returnPressed.connect(self._submit)
        self.input.installEventFilter(self)
        clear_btn = QPushButton("LIMPIAR")
        clear_btn.setObjectName("cliHide")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear)
        input_row.addWidget(prompt)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(clear_btn)
        layout.addLayout(input_row)

        self._append("[duAI Terminal — escribe un comando y presiona Enter]\n")

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._history_back()
                return True
            if key == Qt.Key.Key_Down:
                self._history_forward()
                return True
            if key == Qt.Key.Key_Escape:
                self._kill_process()
                return True
        return super().eventFilter(obj, event)

    def _history_back(self):
        if not self._history:
            return
        if self._history_index < 0:
            self._history_index = len(self._history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self.input.setText(self._history[self._history_index])

    def _history_forward(self):
        if not self._history or self._history_index < 0:
            return
        self._history_index += 1
        if self._history_index >= len(self._history):
            self._history_index = -1
            self.input.setText("")
        else:
            self.input.setText(self._history[self._history_index])

    def _submit(self):
        text = self.input.text().strip()
        if not text:
            return
        self._history.append(text)
        self._history_index = -1
        self.input.clear()
        self._append(f"> {text}\n")

        if text.lower() in ("clear", "limpiar", "cls"):
            self._clear()
            return

        if text.lower() in ("exit", "salir"):
            self._append("[usa el boton CERRAR o el comando del menu para salir de duAI]\n")
            return

        try:
            self._process = subprocess.Popen(
                text,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=None,
            )
            reader = _OutputReader(self._process, self._append_safe)
            reader.start()
            self.input.setEnabled(False)
            reader.join()
            self.input.setEnabled(True)
            self._process = None
        except Exception as exc:
            self._append(f"[ERROR] {exc}\n")
            self._process = None

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._append("\n[Proceso interrumpido]\n")
            except Exception:
                pass

    def _append(self, text):
        self.output.appendPlainText(text.rstrip())
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_safe(self, text):
        from PySide6.QtCore import QMetaObject, Qt

        QMetaObject.invokeMethod(
            self, "_append", Qt.ConnectionType.QueuedConnection,
            _append_slot=lambda: self._append(text),
        )

    def _clear(self):
        self.output.clear()

    def run_command(self, text):
        self.input.setText(text)
        self._submit()
