from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import session as session_core


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

        layout.addSpacing(12)
        action_row = QHBoxLayout()
        self.status = QLabel("SESION INACTIVA")
        self.status.setObjectName("statusLabel")
        self.stop_btn = QPushButton("CERRAR SESION Y DESTRUIR PERFIL")
        self.stop_btn.clicked.connect(self._stop)
        action_row.addWidget(self.status)
        action_row.addStretch(1)
        action_row.addWidget(self.stop_btn)
        layout.addLayout(action_row)

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

    def showEvent(self, event):
        self._refresh_status()
        super().showEvent(event)
