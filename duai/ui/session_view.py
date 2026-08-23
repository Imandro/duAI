from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import session as session_core
from ..core import cli_session


class SessionView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        micro = QLabel("NAVEGACION SIN RASTRO")
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        title = QLabel("Sesion protegida")
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        layout.addWidget(title)

        body = QLabel(
            "Abre la web de IA que elijas en un perfil temporal aislado. Al cerrar la "
            "sesion protegida, el navegador se cierra y todo el perfil (cookies, sesiones, "
            "cache, historial) se destruye. Tu perfil real permanece intacto."
        )
        body.setWordWrap(True)
        body.setObjectName("heroBody")
        body.setMaximumWidth(560)
        layout.addWidget(body)

        browser_row = QHBoxLayout()
        browser_label = QLabel("NAVEGADOR")
        browser_label.setObjectName("microLabel")
        browser_row.addWidget(browser_label)
        self._browser_buttons = []
        self._browser_group = None
        browsers = session_core.available_browsers()
        if browsers:
            from PySide6.QtWidgets import QButtonGroup

            self._browser_group = QButtonGroup(self)
            for index, (browser_id, path) in enumerate(browsers):
                btn = QPushButton(browser_id.upper())
                btn.setCheckable(True)
                btn.setChecked(index == 0)
                btn.setProperty("exe", path)
                self._browser_group.addButton(btn)
                self._browser_buttons.append(btn)
                browser_row.addWidget(btn)
        else:
            none_label = QLabel("NO SE ENCONTRO CHROME, EDGE NI BRAVE")
            none_label.setObjectName("statusLabel")
            browser_row.addWidget(none_label)
        browser_row.addStretch(1)
        layout.addLayout(browser_row)

        sites_label = QLabel("ABRIR SITIO")
        sites_label.setObjectName("microLabel")
        layout.addWidget(sites_label)

        sites_wrap = QVBoxLayout()
        sites_wrap.setSpacing(8)
        row = None
        for index, (name, url) in enumerate(session_core.AI_SITES):
            if index % 4 == 0:
                row = QHBoxLayout()
                row.setSpacing(8)
                sites_wrap.addLayout(row)
            site_btn = QPushButton(name)
            site_btn.clicked.connect(lambda _=False, u=url: self._open(u))
            row.addWidget(site_btn)
            if index == len(session_core.AI_SITES) - 1:
                row.addStretch(1)
        grid_container = QWidget()
        grid_container.setLayout(sites_wrap)
        layout.addWidget(grid_container)

        action_row = QHBoxLayout()
        self.status = QLabel("SESION INACTIVA")
        self.status.setObjectName("statusLabel")
        self.stop_btn = QPushButton("CERRAR SESION Y DESTRUIR PERFIL")
        self.stop_btn.clicked.connect(self._stop)
        action_row.addWidget(self.status)
        action_row.addStretch(1)
        action_row.addWidget(self.stop_btn)
        layout.addLayout(action_row)

        layout.addSpacing(24)

        cli_separator = QLabel("HERRAMIENTAS DE CONSOLA SEGURA")
        cli_separator.setObjectName("toolSectionTitle")
        layout.addWidget(cli_separator)

        cli_body = QLabel(
            "Ejecuta herramientas de IA de consola (opencode, claude, codex, etc.) "
            "en un entorno aislado. Todo lo que escriban queda dentro del sandbox. "
            "Al terminar, se borran los rastros automaticamente."
        )
        cli_body.setWordWrap(True)
        cli_body.setObjectName("heroBody")
        cli_body.setMaximumWidth(560)
        layout.addWidget(cli_body)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        tools = cli_session.list_tools()
        self._cli_btns = {}
        for tool_id, tool_name in tools.items():
            btn = QPushButton(tool_name.upper())
            btn.setObjectName("toolChip")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, tid=tool_id: self._select_tool(tid))
            tools_row.addWidget(btn)
            self._cli_btns[tool_id] = btn
        tools_row.addStretch(1)
        layout.addLayout(tools_row)

        self._selected_tool = None

        cli_action_row = QHBoxLayout()
        self.cli_status = QLabel("")
        self.cli_status.setObjectName("cliSessionStatus")
        self.cli_status.setObjectName("cliSessionIdle")
        cli_action_row.addWidget(self.cli_status)
        cli_action_row.addStretch(1)

        self.select_cwd_btn = QPushButton("CARPETA DE TRABAJO")
        self.select_cwd_btn.setObjectName("toolChip")
        self.select_cwd_btn.clicked.connect(self._select_cwd)
        self._cwd = None
        cli_action_row.addWidget(self.select_cwd_btn)

        self.cli_start_btn = QPushButton("INICIAR SESION SEGURA")
        self.cli_start_btn.clicked.connect(self._start_cli_session)
        cli_action_row.addWidget(self.cli_start_btn)

        self.cli_stop_btn = QPushButton("TERMINAR Y BORRAR RASTROS")
        self.cli_stop_btn.setObjectName("cliHide")
        self.cli_stop_btn.clicked.connect(self._stop_cli_session)
        self.cli_stop_btn.setVisible(False)
        cli_action_row.addWidget(self.cli_stop_btn)

        layout.addLayout(cli_action_row)

        layout.addStretch(1)

    def _selected_browser(self):
        if not self._browser_buttons:
            return None
        checked = next((b for b in self._browser_buttons if b.isChecked()), None)
        return checked.property("exe") if checked else None

    def open_site(self, site_name):
        site = site_name.lower().strip("/")
        url = next((u for name, u in session_core.AI_SITES if name.lower() == site), None)
        if url is None and site_name.startswith("http"):
            url = site_name
        if url is None:
            return False, f"SITIO NO SOPORTADO: {site_name}"
        exe = self._selected_browser()
        if not exe:
            return False, "No hay navegador compatible disponible."
        if session_core.start_session(exe, url):
            self._refresh_status()
            return True, f"SESION PROTEGIDA ACTIVA · {url}"
        return False, "Ya hay una sesion activa. Cierrala antes de abrir otra."

    def stop_action(self):
        if session_core.stop_session():
            self._refresh_status()
            return True, "Sesion cerrada y perfil destruido."
        return False, "[AVISO] el perfil no pudo eliminarse por completo."

    def _open(self, url):
        ok, message = self.open_site(url)
        if not ok:
            QMessageBox.information(self, "duAI", message)

    def _stop(self):
        ok, message = self.stop_action()
        if not ok:
            QMessageBox.warning(self, "duAI", message)

    def _refresh_status(self):
        if session_core.has_running_session():
            current = session_core.get_active_session()
            self.status.setText(f"SESION ACTIVA · {current.url}")
        else:
            self.status.setText("SESION INACTIVA")

    def _select_tool(self, tool_id):
        self._selected_tool = tool_id
        for tid, btn in self._cli_btns.items():
            btn.setChecked(tid == tool_id)

    def _select_cwd(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de trabajo")
        if d:
            self._cwd = d
            self.select_cwd_btn.setText(d.split("/")[-1].split("\\")[-1].upper())

    def _start_cli_session(self):
        if not self._selected_tool:
            QMessageBox.information(self, "duAI", "Selecciona una herramienta primero.")
            return
        session = cli_session.start_session(self._selected_tool, cwd=self._cwd)
        if session:
            self.mw.navigate(6)
            self.mw.terminal_view._launch_tool(self._selected_tool)
            self._refresh_cli_status()
        else:
            QMessageBox.warning(self, "duAI", "No se pudo iniciar la sesion. Verifica que la herramienta este instalada.")

    def _stop_cli_session(self):
        cli_session.stop_session()
        if hasattr(self.mw, "terminal_view"):
            self.mw.terminal_view._stop_session()
        self._refresh_cli_status()

    def _refresh_cli_status(self):
        session = cli_session.get_active_session()
        if session and session.is_running:
            tool = cli_session.CLI_TOOLS.get(session.tool_id, {})
            self.cli_status.setText(f"SESIÓN ACTIVA: {tool.get('name', '').upper()}")
            self.cli_status.setObjectName("cliSessionActive")
            self.cli_stop_btn.setVisible(True)
            self.cli_start_btn.setVisible(False)
        else:
            self.cli_status.setText("SIN SESION ACTIVA")
            self.cli_status.setObjectName("cliSessionIdle")
            self.cli_stop_btn.setVisible(False)
            self.cli_start_btn.setVisible(True)
        self.cli_status.style().unpolish(self.cli_status)
        self.cli_status.style().polish(self.cli_status)

    def showEvent(self, event):
        self._refresh_status()
        self._refresh_cli_status()
        super().showEvent(event)
