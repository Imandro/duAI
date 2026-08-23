import os
import re
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ANSI_RE = re.compile(
    r'(\x1b\[[0-9;]*[a-zA-Z])'
    r'|(\x1b\][^\x07]*\x07)'
    r'|(\x1b[()][AB012])'
    r'|(\x1b[=>])'
    r'|(\x1b\[[?][0-9;]*[a-zA-Z])'
)


def _strip_ansi(text):
    return _ANSI_RE.sub('', text).replace('\r', '')


class _PtyReader(threading.Thread):
    def __init__(self, process, callback):
        super().__init__(daemon=True)
        self.process = process
        self.callback = callback
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.process.read(4096)
                if data:
                    self.callback(data)
                else:
                    break
            except EOFError:
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
        self._pending = ""
        self._pending_lock = threading.Lock()
        self._history = []
        self._history_index = -1
        self._cli_session = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(12)

        header = QLabel("TERMINAL")
        header.setObjectName("microLabel")
        layout.addWidget(header)

        self.tool_bar = QHBoxLayout()
        self.tool_bar.setSpacing(6)
        from ..core.cli_session import list_tools
        tools = list_tools()
        self._tool_btns = {}
        for tool_id, tool_name in tools.items():
            btn = QPushButton(tool_name.upper())
            btn.setObjectName("toolChip")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, tid=tool_id: self._launch_tool(tid))
            self.tool_bar.addWidget(btn)
            self._tool_btns[tool_id] = btn
        self.tool_bar.addStretch(1)
        self.session_status = QLabel("")
        self.session_status.setObjectName("cliSessionIdle")
        self.tool_bar.addWidget(self.session_status)
        self.stop_btn = QPushButton("X")
        self.stop_btn.setObjectName("cliHide")
        self.stop_btn.setFixedSize(28, 28)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_session)
        self.tool_bar.addWidget(self.stop_btn)
        layout.addLayout(self.tool_bar)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("terminalOutput")
        self.output.setMaximumBlockCount(3000)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.output.setFont(font)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.input = QLineEdit()
        self.input.setObjectName("terminalInput")
        self.input.setPlaceholderText("Escribe un comando...")
        self.input.returnPressed.connect(self._submit)
        self.input.installEventFilter(self)
        font_in = QFont("Consolas", 10)
        font_in.setStyleHint(QFont.StyleHint.Monospace)
        self.input.setFont(font_in)
        input_row.addWidget(self.input, 1)
        layout.addLayout(input_row)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.setInterval(30)

        self._start_pty()

    def _start_pty(self, env=None, cwd=None):
        try:
            from winpty.ptyprocess import PtyProcess
            self._pty = PtyProcess.spawn(
                "powershell.exe -NoLogo -NoProfile",
                cwd=cwd or os.path.expandvars("%USERPROFILE%"),
                env=env or os.environ.copy(),
                dimensions=(50, 140),
            )
            self._reader = _PtyReader(self._pty, self._on_data)
            self._reader.start()
            self._poll_timer.start()
        except ImportError:
            self._append_text("[pywinpty no instalado]\n")
        except Exception as exc:
            self._append_text(f"[Error PTY: {exc}]\n")

    def _launch_tool(self, tool_id):
        from ..core.cli_session import CLI_TOOLS, _create_sandbox, _build_env

        tool = CLI_TOOLS.get(tool_id)
        if not tool:
            return

        cwd = QFileDialog.getExistingDirectory(self, f"Carpeta para {tool['name']}")
        if not cwd:
            cwd = os.path.expandvars("%USERPROFILE%")

        sandbox = _create_sandbox(tool_id)
        env = _build_env(tool_id, sandbox)

        self._stop_pty()
        self.output.clear()
        self._append_text(f"[Sesion: {tool['name']}] -> {cwd}\n")

        self._start_pty(env=env, cwd=cwd)

        self._cli_session = type("_S", (), {
            "sandbox": sandbox,
            "tool_id": tool_id,
            "is_running": True,
        })()

        self.session_status.setText(tool['name'].upper())
        self.session_status.setObjectName("cliSessionActive")
        self.session_status.style().unpolish(self.session_status)
        self.session_status.style().polish(self.session_status)
        self.stop_btn.setVisible(True)
        for tid, btn in self._tool_btns.items():
            btn.setEnabled(tid != tool_id)

    def _stop_session(self):
        if self._cli_session:
            from ..core.cli_session import _purge_powershell_history_ai
            import shutil
            sandbox = getattr(self._cli_session, "sandbox", None)
            self._stop_pty()
            if sandbox and os.path.isdir(sandbox):
                try:
                    shutil.rmtree(sandbox, ignore_errors=True)
                except Exception:
                    pass
            _purge_powershell_history_ai()
            self._cli_session = None
            self.session_status.setText("")
            self.session_status.setObjectName("cliSessionIdle")
            self.session_status.style().unpolish(self.session_status)
            self.session_status.style().polish(self.session_status)
            self.stop_btn.setVisible(False)
            for btn in self._tool_btns.values():
                btn.setEnabled(True)
            self._append_text("[Sesion cerrada]\n")
            self._start_pty()

    def _stop_pty(self):
        self._poll_timer.stop()
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._pty:
            try:
                self._pty.close(force=True)
            except Exception:
                try:
                    self._pty.terminate(force=True)
                except Exception:
                    pass
            self._pty = None
        with self._pending_lock:
            self._pending = ""

    def _on_data(self, data):
        clean = _strip_ansi(data)
        if clean:
            with self._pending_lock:
                self._pending += clean

    def _poll(self):
        with self._pending_lock:
            pending = self._pending
            self._pending = ""
        if pending:
            self._append_text(pending)

    def _append_text(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

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
                if self._cli_session:
                    self._stop_session()
                else:
                    self._send_ctrl_c()
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

        if text.lower() in ("clear", "cls"):
            self._clear()
            return

        if self._pty:
            try:
                self._pty.write(text + "\r\n")
            except EOFError:
                self._append_text("[Sesion cerrada]\n")
        else:
            self._append_text(f"> {text}\n")

    def _send_ctrl_c(self):
        if self._pty:
            try:
                self._pty.write("\x03")
            except EOFError:
                pass

    def _clear(self):
        self.output.clear()

    def run_command(self, text):
        self.input.setText(text)
        self._submit()

    def closeEvent(self, event):
        if self._cli_session:
            from ..core.cli_session import stop_session
            stop_session()
        self._stop_pty()
        super().closeEvent(event)
