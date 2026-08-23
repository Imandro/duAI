from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QVBoxLayout,
    QWidget,
)

from ..core.system_clean import hosts_block_active, set_hosts_block
from ..security import auth
from ..utils.logger import open_logs_folder
from ..utils.settings import get_settings


class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel("CONFIGURACION")
        micro.setObjectName("microLabel")
        outer.addWidget(micro)
        title = QLabel("Ajustes")
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(24)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._build_password(layout)
        self._build_exclusions(layout)
        self._build_stealth(layout)
        self._build_float_widget(layout)
        self._build_uninstall(layout)
        self._build_quarantine(layout)
        self._build_hosts(layout)
        self._build_scheduler(layout)
        self._build_logs(layout)
        layout.addStretch(1)

    def _section(self, parent_layout, caption):
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        box = QVBoxLayout(frame)
        box.setContentsMargins(0, 14, 0, 6)
        box.setSpacing(10)
        label = QLabel(caption.upper())
        label.setObjectName("microLabel")
        box.addWidget(label)
        parent_layout.addWidget(frame)
        return box

    def _build_password(self, layout):
        box = self._section(layout, "Contrasena de acceso")
        note = QLabel(
            "Protege duAI con contrasena. Se guarda localmente con derivacion PBKDF2."
            if auth.has_password()
            else "Sin contrasena. Cualquiera con acceso a tu sesion puede abrir duAI."
        )
        note.setObjectName("heroBody")
        note.setWordWrap(True)
        box.addWidget(note)

        row = QHBoxLayout()
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Nueva contrasena")
        self.pw_confirm = QLineEdit()
        self.pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_confirm.setPlaceholderText("Confirmar")
        set_btn = QPushButton("ESTABLECER")
        set_btn.clicked.connect(self._set_password)
        clear_btn = QPushButton("QUITAR")
        clear_btn.clicked.connect(self._clear_password)
        for widget in (self.pw_input, self.pw_confirm, set_btn, clear_btn):
            row.addWidget(widget)
        box.addLayout(row)

    def _set_password(self):
        pw = self.pw_input.text()
        if len(pw) < 4:
            QMessageBox.information(self, "duAI", "Usa al menos 4 caracteres.")
            return
        if pw != self.pw_confirm.text():
            QMessageBox.information(self, "duAI", "Las contrasenas no coinciden.")
            return
        auth.set_password(pw)
        self.pw_input.clear()
        self.pw_confirm.clear()
        QMessageBox.information(self, "duAI", "Contrasena establecida.")

    def _clear_password(self):
        if not auth.has_password():
            return
        auth.clear_password()
        QMessageBox.information(self, "duAI", "Contrasena eliminada.")

    def _build_exclusions(self, layout):
        box = self._section(layout, "Exclusiones (nunca se limpian)")
        from ..core.targets import list_all_entries

        settings = get_settings()
        exclusions = set(settings.get("exclusions") or [])
        self.exclusion_checks = {}
        for entry in list_all_entries():
            check = QCheckBox(entry["category"] + " · " + entry["name"])
            check.setChecked(entry["id"] in exclusions)
            check.toggled.connect(lambda state, tid=entry["id"]: self._toggle_exclusion(tid, state))
            box.addWidget(check)

    def _toggle_exclusion(self, target_id, state):
        settings = get_settings()
        exclusions = set(settings.get("exclusions") or [])
        if state:
            exclusions.add(target_id)
        else:
            exclusions.discard(target_id)
        settings.set("exclusions", sorted(exclusions))

    def _build_stealth(self, layout):
        box = self._section(layout, "Modo sigilo")
        self.purge_check = QCheckBox("PURGAR LOS REGISTROS DE duAI AL CERRAR")
        self.purge_check.setChecked(bool(get_settings().get("self_purge_on_exit")))
        self.purge_check.toggled.connect(
            lambda state: get_settings().set("self_purge_on_exit", bool(state))
        )
        box.addWidget(self.purge_check)
        hint = QLabel(
            "Con el modo sigilo activo, duAI borra su propia bitacora local y los accesos "
            "recientes que lo mencionen cada vez que se cierra."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)
        row = QHBoxLayout()
        wipe_btn = QPushButton("ELIMINAR TODOS LOS DATOS DE duAI")
        wipe_btn.clicked.connect(self._wipe_own_data)
        row.addWidget(wipe_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _wipe_own_data(self):
        confirm = QMessageBox.question(
            self,
            "duAI",
            "Se eliminaran la configuracion, la contrasena, las exclusiones, la cuarentena "
            "y los registros de duAI. La aplicacion se cerrara despues. Continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from ..core.selfclean import purge_all_local_data

        purge_all_local_data()
        QMessageBox.information(self, "duAI", "Datos locales eliminados.")
        self.mw.close()

    def _build_quarantine(self, layout):
        from ..core.quarantine import quarantined_items

        box = self._section(layout, "Cuarentena restaurable")
        items = quarantined_items()
        count_label = QLabel(f"{len(items)} elementos en cuarentena.")
        count_label.setObjectName("heroBody")
        box.addWidget(count_label)
        row = QHBoxLayout()
        restore_btn = QPushButton("RESTAURAR TODO")
        restore_btn.clicked.connect(self._restore_quarantine)
        purge_btn = QPushButton("VACIAR CUARENTENA")
        purge_btn.clicked.connect(self._purge_quarantine)
        row.addWidget(restore_btn)
        row.addWidget(purge_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _build_float_widget(self, layout):
        box = self._section(layout, "Boton flotante de panico")
        self.float_check = QCheckBox("MOSTRAR BOTON FLOTANTE EN PANTALLA")
        self.float_check.setChecked(bool(get_settings().get("float_visible")))
        self.float_check.toggled.connect(self._toggle_float)
        box.addWidget(self.float_check)
        hint = QLabel(
            "Widget always-on-top que se puede arrastrar. "
            "Click izquierdo ejecuta panico, click derecho muestra opciones."
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

        size_row = QHBoxLayout()
        size_label = QLabel("TAMANO")
        size_label.setObjectName("microLabel")
        size_row.addWidget(size_label)
        from PySide6.QtWidgets import QSpinBox
        self.float_size = QSpinBox()
        self.float_size.setRange(80, 300)
        self.float_size.setSingleStep(10)
        current = get_settings().get("float_size") or 132
        self.float_size.setValue(current)
        self.float_size.setSuffix(" px")
        self.float_size.valueChanged.connect(self._change_float_size)
        size_row.addWidget(self.float_size)
        size_row.addStretch(1)
        box.addLayout(size_row)

    def _toggle_float(self, state):
        get_settings().set("float_visible", bool(state))
        if state:
            self.mw.show_panic_float()
        else:
            self.mw.hide_panic_float()

    def _change_float_size(self, value):
        get_settings().set("float_size", value)
        if self.mw._float_widget:
            self.mw._float_widget.setFixedSize(value, value)
            self.mw._float_widget.button.setStyleSheet(
                f"font-size: {max(12, value // 5)}px;"
            )

    def _build_uninstall(self, layout):
        from ..core.uninstaller import find_installed_ai_apps

        box = self._section(layout, "Desinstalacion avanzada de apps de IA")
        warning = QLabel(
            "ZONA AVANZADA. Desinstala completamente las aplicaciones seleccionadas y despues "
            "limpia sus rastros locales (cache, registro, historial). La accion no se puede deshacer: "
            "las apps desaparecen del equipo, no solo sus rastros."
        )
        warning.setObjectName("heroBody")
        warning.setWordWrap(True)
        box.addWidget(warning)

        try:
            self._apps = find_installed_ai_apps()
        except Exception:
            self._apps = []

        if not self._apps:
            empty = QLabel("No se detectaron aplicaciones de IA instaladas.")
            empty.setObjectName("statusLabel")
            box.addWidget(empty)
            return

        self._uninstall_checks = {}
        for app in self._apps:
            quiet = "silenciable" if app["quiet_string"] else "asistido"
            check = QCheckBox(f"{app['name']}  ·  {quiet}")
            self._uninstall_checks[app["name"]] = check
            box.addWidget(check)

        row = QHBoxLayout()
        uninstall_btn = QPushButton("DESINSTALAR SELECCIONADAS Y LIMPIAR RASTROS")
        uninstall_btn.clicked.connect(self._uninstall_selected)
        refresh_btn = QPushButton("REDETECTAR")
        refresh_btn.clicked.connect(lambda: self.mw.refresh_settings_page())
        row.addWidget(uninstall_btn)
        row.addWidget(refresh_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _uninstall_selected(self):
        selected = [
            app for app in getattr(self, "_apps", [])
            if self._uninstall_checks.get(app["name"]) and self._uninstall_checks[app["name"]].isChecked()
        ]
        if not selected:
            QMessageBox.information(self, "duAI", "Marca al menos una aplicacion para desinstalar.")
            return
        names = "\n".join("· " + app["name"] for app in selected)
        confirm = QMessageBox.question(
            self,
            "duAI",
            "Se desinstalaran estas aplicaciones y se borraran sus rastros:\n\n"
            + names
            + "\n\nContinuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        from .worker import Worker

        def job():
            results = []
            from ..core.uninstaller import run_uninstall, clean_traces_for_app

            for app in selected:
                ok, detail = run_uninstall(app)
                cleaned = clean_traces_for_app(app["name"]) if ok else None
                results.append((app["name"], ok, detail, cleaned))
            return results

        def done(results):
            lines = []
            for name, ok, detail, cleaned in results:
                if ok:
                    extra = ""
                    if cleaned is not None:
                        extra = f" · rastros: {cleaned.removed_items} elementos, {cleaned.freed_bytes} bytes liberados"
                    lines.append(f"[OK] {name} ({detail}){extra}")
                else:
                    lines.append(f"[FALLO] {name}: {detail}")
            QMessageBox.information(self, "duAI", "\n".join(lines))
            self.mw.refresh_settings_page()

        self.mw.run_cli_worker(job, done)

    def _restore_quarantine(self):
        from ..core.quarantine import restore_all

        restored = restore_all()
        QMessageBox.information(self, "duAI", f"{restored} elementos restaurados.")
        self.mw.refresh_settings_page()

    def _purge_quarantine(self):
        from ..core.quarantine import purge_quarantine

        removed = purge_quarantine()
        QMessageBox.information(self, "duAI", f"Cuarentena vaciada ({removed} elementos).")
        self.mw.refresh_settings_page()

    def _build_hosts(self, layout):
        box = self._section(layout, "Bloqueo de telemetria de IA (archivo hosts)")
        self.hosts_check = QCheckBox("REDIRIGIR DOMINIOS DE TELEMETRIA A 0.0.0.0")
        self.hosts_check.setChecked(hosts_block_active())
        apply_btn = QPushButton("APLICAR")
        apply_btn.clicked.connect(self._apply_hosts)
        row = QHBoxLayout()
        row.addWidget(self.hosts_check)
        row.addStretch(1)
        row.addWidget(apply_btn)
        box.addLayout(row)
        hint = QLabel("Requiere ejecutar duAI como administrador para modificar el archivo hosts.")
        hint.setObjectName("statusLabel")
        box.addWidget(hint)

    def _apply_hosts(self):
        try:
            set_hosts_block(self.hosts_check.isChecked())
            QMessageBox.information(self, "duAI", "Archivo hosts actualizado.")
        except PermissionError:
            QMessageBox.warning(
                self, "duAI",
                "Permisos insuficientes. Ejecuta duAI como administrador e intentalo de nuevo.",
            )

    def _build_scheduler(self, layout):
        box = self._section(layout, "Programador de Windows")
        from ..core.scheduler import logon_task_exists

        exists = logon_task_exists()
        state = QLabel(
            "Tarea activa: duAI se limpia automaticamente en cada inicio de sesion."
            if exists
            else "Sin tarea programada."
        )
        state.setObjectName("heroBody")
        box.addWidget(state)
        row = QHBoxLayout()
        create_btn = QPushButton("CREAR TAREA AL INICIAR SESION")
        create_btn.clicked.connect(self._create_task)
        remove_btn = QPushButton("ELIMINAR TAREA")
        remove_btn.clicked.connect(self._remove_task)
        row.addWidget(create_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _create_task(self):
        from ..core.scheduler import create_logon_task

        if create_logon_task():
            QMessageBox.information(self, "duAI", "Tarea creada.")
        else:
            QMessageBox.warning(self, "duAI", "No se pudo crear la tarea.")

    def _remove_task(self):
        from ..core.scheduler import remove_logon_task

        if remove_logon_task():
            QMessageBox.information(self, "duAI", "Tarea eliminada.")
        else:
            QMessageBox.warning(self, "duAI", "No se pudo eliminar la tarea (puede que no exista).")

    def _build_logs(self, layout):
        box = self._section(layout, "Registro local")
        row = QHBoxLayout()
        open_btn = QPushButton("ABRIR CARPETA DE REGISTROS")
        open_btn.clicked.connect(open_logs_folder)
        export_btn = QPushButton("GUARDAR COPIA DE CONFIGURACION")
        export_btn.clicked.connect(self._export_config)
        row.addWidget(open_btn)
        row.addWidget(export_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _export_config(self):
        import json

        path, _ = QFileDialog.getSaveFileName(self, "Guardar configuracion", "duai_config.json", "JSON (*.json)")
        if not path:
            return
        data = getattr(get_settings(), "_data", {})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {k: v for k, v in data.items() if k != "password_hash"},
                fh, indent=2, ensure_ascii=False,
            )
