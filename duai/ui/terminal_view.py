import os
import subprocess
import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TerminalView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._cli_session = None
        self._process = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(12)

        header = QLabel("TERMINAL")
        header.setObjectName("microLabel")
        layout.addWidget(header)

        title = QLabel("Herramientas de IA")
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        layout.addWidget(title)

        hint = QLabel(
            "Abre una sesion aislada de cualquier herramienta de IA en una ventana de "
            "PowerShell real. Todo queda dentro del sandbox y se borra al salir."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        hint.setMaximumWidth(560)
        layout.addWidget(hint)

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
        layout.addLayout(self.tool_bar)

        self.cwd_row = QHBoxLayout()
        self.cwd_label = QLabel("CARPETA DE TRABAJO:")
        self.cwd_label.setObjectName("microLabel")
        self.cwd_path = QLabel(os.path.expandvars("%USERPROFILE%"))
        self.cwd_path.setObjectName("heroBody")
        self.cwd_btn = QPushButton("CAMBIAR")
        self.cwd_btn.setObjectName("cliHide")
        self.cwd_btn.setFixedHeight(28)
        self.cwd_btn.clicked.connect(self._pick_cwd)
        self.cwd_row.addWidget(self.cwd_label)
        self.cwd_row.addWidget(self.cwd_path, 1)
        self.cwd_row.addWidget(self.cwd_btn)
        layout.addLayout(self.cwd_row)

        layout.addSpacing(8)

        status_row = QHBoxLayout()
        self.session_status = QLabel("SIN SESION ACTIVA")
        self.session_status.setObjectName("cliSessionIdle")
        status_row.addWidget(self.session_status)
        status_row.addStretch(1)
        self.stop_btn = QPushButton("CERRAR SESION Y BORRAR RASTROS")
        self.stop_btn.setObjectName("cliHide")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_session)
        status_row.addWidget(self.stop_btn)
        layout.addLayout(status_row)

        layout.addStretch(1)

        info = QLabel(
            "PowerShell se abre en una ventana real con entorno aislado. "
            "Al cerrar la ventana se borraran automaticamente los rastros."
        )
        info.setObjectName("hintLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

    def _pick_cwd(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de trabajo")
        if d:
            self.cwd_path.setText(d)

    def _launch_tool(self, tool_id):
        from ..core.cli_session import CLI_TOOLS, _create_sandbox, _build_env

        tool = CLI_TOOLS.get(tool_id)
        if not tool:
            return

        if self._cli_session and self._cli_session.get("process"):
            QMessageBox.information(self, "duAI", "Cierra la sesion actual primero.")
            return

        cwd = self.cwd_path.text()
        sandbox = _create_sandbox(tool_id)
        env = _build_env(tool_id, sandbox)

        env_args = " ".join(f'$env:{k}="{v}";' for k, v in env.items()
                           if k not in os.environ or os.environ.get(k) != v)

        ps_cmd = (
            f'Set-Location "{cwd}"; '
            f'Write-Host "========================================" -ForegroundColor DarkRed; '
            f'Write-Host "  duAI SESION SEGURA: {tool["name"]}" -ForegroundColor Red; '
            f'Write-Host "  Sandbox: {sandbox}" -ForegroundColor DarkGray; '
            f'Write-Host "  CWD: {cwd}" -ForegroundColor DarkGray; '
            f'Write-Host "  Al cerrar esta ventana se borrara todo." -ForegroundColor DarkRed; '
            f'Write-Host "========================================" -ForegroundColor DarkRed; '
            f'Write-Host ""'
        )

        exe = tool["exe"]
        cmd_parts = env_args.split("; ") if env_args else []
        full_cmd = f'powershell.exe -NoExit -Command "{ps_cmd} {exe}"'

        try:
            proc = subprocess.Popen(
                full_cmd,
                shell=True,
                cwd=cwd,
                env=env,
            )
            self._process = proc
            self._cli_session = {
                "tool_id": tool_id,
                "sandbox": sandbox,
                "process": proc,
                "start_time": time.time(),
            }

            self.session_status.setText(f"ACTIVA: {tool['name'].upper()}")
            self.session_status.setObjectName("cliSessionActive")
            self.session_status.style().unpolish(self.session_status)
            self.session_status.style().polish(self.session_status)
            self.stop_btn.setVisible(True)
            for tid, btn in self._tool_btns.items():
                btn.setEnabled(tid != tool_id)

            self._watch_process()

        except Exception as exc:
            QMessageBox.warning(self, "duAI", f"No se pudo iniciar: {exc}")

    def _watch_process(self):
        def _check():
            while self._cli_session and self._cli_session.get("process"):
                proc = self._cli_session["process"]
                if proc.poll() is not None:
                    self._on_process_exit()
                    return
                time.sleep(1)

        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _on_process_exit(self):
        if self._cli_session:
            from ..core.cli_session import _purge_powershell_history_ai
            import shutil
            sandbox = self._cli_session.get("sandbox")
            if sandbox and os.path.isdir(sandbox):
                try:
                    shutil.rmtree(sandbox, ignore_errors=True)
                except Exception:
                    pass
            _purge_powershell_history_ai()
            self._cli_session = None
            self._process = None
            QTimer.singleShot(0, self._reset_ui)

    def _reset_ui(self):
        self.session_status.setText("SIN SESION ACTIVA")
        self.session_status.setObjectName("cliSessionIdle")
        self.session_status.style().unpolish(self.session_status)
        self.session_status.style().polish(self.session_status)
        self.stop_btn.setVisible(False)
        for btn in self._tool_btns.values():
            btn.setEnabled(True)

    def _stop_session(self):
        if self._cli_session:
            from ..core.cli_session import _purge_powershell_history_ai
            import shutil
            proc = self._cli_session.get("process")
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            sandbox = self._cli_session.get("sandbox")
            if sandbox and os.path.isdir(sandbox):
                try:
                    shutil.rmtree(sandbox, ignore_errors=True)
                except Exception:
                    pass
            _purge_powershell_history_ai()
            self._cli_session = None
            self._process = None
            self._reset_ui()

    def run_command(self, text):
        pass

    def closeEvent(self, event):
        if self._cli_session:
            self._stop_session()
        super().closeEvent(event)
