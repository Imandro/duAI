import queue
import subprocess
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _Reader(threading.Thread):
    def __init__(self, proc, out_queue):
        super().__init__(daemon=True)
        self.proc = proc
        self.q = out_queue

    def run(self):
        try:
            for line in iter(self.proc.stdout.readline, ""):
                if not line:
                    break
                self.q.put(line.rstrip("\n"))
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except Exception:
            pass
        self.q.put(None)


class TerminalView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._process = None
        self._reader = None
        self._queue = queue.Queue()
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
            "PowerShell integrado — escribe comandos directamente. "
            "Escribe 'opencode' para iniciar OpenCode."
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
        prompt = QLabel("PS>")
        prompt.setObjectName("promptMark")
        self.input = QLineEdit()
        self.input.setObjectName("terminalInput")
        self.input.setPlaceholderText("Escribe un comando de PowerShell...")
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

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.setInterval(60)

        self._append("[duAI Terminal — PowerShell]\n")
        self._append("[Escribe 'opencode' para iniciar OpenCode]\n")

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
        self._append(f"PS> {text}\n")

        if text.lower() in ("clear", "cls"):
            self._clear()
            return

        try:
            self._process = subprocess.Popen(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", text],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self._queue = queue.Queue()
            self._reader = _Reader(self._process, self._queue)
            self._reader.start()
            self.input.setEnabled(False)
            self._poll_timer.start()
        except Exception as exc:
            self._append(f"[ERROR] {exc}\n")

    def _poll(self):
        try:
            while True:
                line = self._queue.get_nowait()
                if line is None:
                    self._poll_timer.stop()
                    rc = self._process.returncode if self._process else "?"
                    self._append(f"\n[Proceso finalizado — codigo {rc}]\n")
                    self._process = None
                    self._reader = None
                    self.input.setEnabled(True)
                    self.input.setFocus()
                    return
                self._append(line)
        except queue.Empty:
            pass

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._append("\n[Proceso interrumpido]\n")
            except Exception:
                pass
            self._poll_timer.stop()
            self._process = None
            self._reader = None
            self.input.setEnabled(True)

    def _append(self, text):
        self.output.appendPlainText(text)
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self):
        self.output.clear()

    def run_command(self, text):
        self.input.setText(text)
        self._submit()
