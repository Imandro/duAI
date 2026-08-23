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


class _PtyReader(threading.Thread):
    def __init__(self, pty, callback):
        super().__init__(daemon=True)
        self.pty = pty
        self.callback = callback
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.pty.read(4096)
                if data:
                    self.callback(data)
                else:
                    break
            except Exception:
                break

    def stop(self):
        self.running = False


class TerminalView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._pty = None
        self._reader = None
        self._history = []
        self._history_index = -1
        self._input_buffer = ""

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
            "Terminal real (PTY) — ejecuta cualquier app de consola: "
            "opencode, claude, codex, gemini cli, etc."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        hint.setMaximumWidth(560)
        layout.addWidget(hint)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("terminalOutput")
        self.output.setMaximumBlockLines(5000)
        layout.addWidget(self.output, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        prompt = QLabel("PS>")
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

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.setInterval(30)

        self._start_pty()
        self._append_line("[Terminal PTY iniciado — PowerShell listo]\n")
        self._append_line("[Escribe comandos directamente o usa la pestaña TERMINAL para mas espacio]\n")

    def _start_pty(self):
        try:
            import winpty
            self._pty = winpty.Pty(shell="powershell.exe")
            self._reader = _PtyReader(self._pty, self._on_data)
            self._reader.start()
            self._poll_timer.start()
        except Exception as exc:
            self._append_line(f"[ERROR] No se pudo iniciar PTY: {exc}\n")
            self._append_line("[Usa la pestana TERMINAL para PowerShell basico]\n")

    def _on_data(self, data):
        self._pending = getattr(self, "_pending", "") + data

    def _poll(self):
        pending = getattr(self, "_pending", "")
        if pending:
            self._pending = ""
            self._append_text(pending)

    def _append_text(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_line(self, text):
        self._append_text(text)

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
                self._kill()
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
        text = self.input.text()
        self._history.append(text)
        self._history_index = -1
        self.input.clear()

        if text.lower() in ("clear", "cls"):
            self._clear()
            return

        if self._pty:
            self._pty.write(text + "\r\n")
        else:
            self._append_line(f"PS> {text}\n")

    def _kill(self):
        if self._pty:
            try:
                self._pty.kill()
            except Exception:
                pass
            self._poll_timer.stop()
            self._append_line("\n[Proceso interrumpido]\n")
            self._start_pty()

    def _clear(self):
        self.output.clear()

    def run_command(self, text):
        self.input.setText(text)
        self._submit()

    def closeEvent(self, event):
        if self._reader:
            self._reader.stop()
        if self._pty:
            try:
                self._pty.kill()
            except Exception:
                pass
        super().closeEvent(event)
