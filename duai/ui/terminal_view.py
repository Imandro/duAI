import os
import threading

from PySide6.QtCore import Qt, QTimer, Signal
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
        self._cli_session = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(12)

        header = QLabel("TERMINAL DEL SISTEMA")
        header.setObjectName("microLabel")
        layout.addWidget(header)

        title = QLabel("Consola")
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        layout.addWidget(title)

        hint = QLabel(
            "Terminal real (PTY) — ejecuta cualquier app de consola: "
            "opencode, claude, codex, gemini cli, etc."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        hint.setMaximumWidth(560)
        layout.addWidget(hint)

        self.tool_bar = QHBoxLayout()
        self.tool_bar.setSpacing(8)
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
        self.cwd_label = QLabel("")
        self.cwd_label.setObjectName("hintLabel")
        self.tool_bar.addWidget(self.cwd_label)
        layout.addLayout(self.tool_bar)

        status_row = QHBoxLayout()
        self.session_status = QLabel("")
        self.session_status.setObjectName("cliSessionStatus")
        self.session_status.setObjectName("cliSessionIdle")
        status_row.addWidget(self.session_status)
        status_row.addStretch(1)
        self.stop_btn = QPushButton("TERMINAR SESION")
        self.stop_btn.setObjectName("cliHide")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_session)
        status_row.addWidget(self.stop_btn)
        layout.addLayout(status_row)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("terminalOutput")
        self.output.setMaximumBlockCount(5000)
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

    def _start_pty(self, env=None, cwd=None):
        try:
            from winpty.ptyprocess import PtyProcess
            cmd = "powershell.exe"
            self._pty = PtyProcess.spawn(
                cmd,
                cwd=cwd or os.path.expandvars("%USERPROFILE%"),
                env=env or os.environ.copy(),
                dimensions=(40, 120),
            )
            self._reader = _PtyReader(self._pty, self._on_data)
            self._reader.start()
            self._poll_timer.start()
        except ImportError:
            self._append_line("[ERROR] pywinpty no instalado — instala con: pip install pywinpty\n")
        except Exception as exc:
            self._append_line(f"[ERROR] No se pudo iniciar PTY: {exc}\n")

    def _launch_tool(self, tool_id):
        from ..core.cli_session import CLISession, CLI_TOOLS, _create_sandbox, _build_env

        tool = CLI_TOOLS.get(tool_id)
        if not tool:
            return

        cwd = QFileDialog.getExistingDirectory(self, f"Seleccionar carpeta para {tool['name']}")
        if not cwd:
            cwd = os.path.expandvars("%USERPROFILE%")

        sandbox = _create_sandbox(tool_id)
        env = _build_env(tool_id, sandbox)

        self._stop_pty()
        self.output.clear()
        self._append_line(f"[Sesión segura: {tool['name']}] Carpeta: {cwd}\n")
        self._append_line(f"[Sandbox: {sandbox}]\n")
        self._append_line(f"[Todo lo que escribas queda aislado. Al salir se borrará automáticamente.]\n\n")

        self._start_pty(env=env, cwd=cwd)

        self._cli_session = type("_S", (), {
            "sandbox": sandbox,
            "tool_id": tool_id,
            "is_running": True,
        })()

        self.session_status.setText(f"SESIÓN ACTIVA: {tool['name'].upper()}")
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
            self._append_line("\n[Sesión terminada — rastros eliminados]\n")
            self._start_pty()

    def _stop_pty(self):
        if self._reader:
            self._reader.stop()
        if self._pty:
            try:
                self._pty.kill(0)
            except Exception:
                try:
                    self._pty.terminate(0)
                except Exception:
                    pass
            self._poll_timer.stop()
            self._pty = None
            self._reader = None

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
                if self._cli_session:
                    self._stop_session()
                else:
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
            self._pty.write(text.encode() + b"\r\n")
        else:
            self._append_line(f"PS> {text}\n")

    def _kill(self):
        if self._pty:
            try:
                self._pty.kill(0)
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
        if self._cli_session:
            from ..core.cli_session import stop_session
            stop_session()
        if self._reader:
            self._reader.stop()
        if self._pty:
            try:
                self._pty.kill(0)
            except Exception:
                pass
        super().closeEvent(event)
