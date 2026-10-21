"""Pestaña Privacidad de ajustes (stealth, hosts, auto-clean, datos).

Extraido de duai/ui/settings_view.py. API: PrivacyTab(main_window) -> QWidget
con atributo .scroll (QScrollArea).
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QFrame,
)

from duai.core.auto_clean import get_auto_clean_service
from duai.i18n import t
from duai.utils.settings import get_settings
from .base import SettingsTab


class PrivacyTab(SettingsTab):
    """Pestaña Privacidad."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_stealth(layout)
        self._build_hosts(layout)
        self._build_auto_clean(layout)
        self._build_data_controls(layout)
        layout.addStretch(1)

    # ---------- stealth ----------
    def _build_stealth(self, layout):
        box = self._section(layout, t("set.stealth_section"))

        self.purge_check = QCheckBox(t("set.stealth_check"))
        self.purge_check.setChecked(bool(get_settings().get("self_purge_on_exit")))
        self.purge_check.toggled.connect(
            lambda state: get_settings().set("self_purge_on_exit", bool(state))
        )
        box.addWidget(self.purge_check)

        hint = QLabel(t("set.stealth_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

        row = QHBoxLayout()
        wipe_btn = QPushButton(t("set.self_destruct"))
        wipe_btn.setObjectName("dangerBtn")
        wipe_btn.clicked.connect(self._wipe_own_data)
        row.addWidget(wipe_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _wipe_own_data(self):
        confirm = QMessageBox.question(
            self, "duAI", t("set.self_destruct_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from duai.core.selfclean import purge_all_local_data
        result = purge_all_local_data()
        if result.get("success"):
            QMessageBox.information(self, "duAI", t("set.data_deleted"))
        else:
            QMessageBox.warning(
                self, "duAI",
                t("set.data_deleted_partial", errors="; ".join(result.get("errors", [])))
            )
        self.mw.close()

    # ---------- hosts ----------
    def _build_hosts(self, layout):
        from duai.core.system_clean import hosts_block_active

        box = self._section(layout, t("set.hosts_section"))

        self.hosts_check = QCheckBox(t("set.hosts_check"))
        self.hosts_check.setChecked(hosts_block_active())
        box.addWidget(self.hosts_check)

        row = QHBoxLayout()
        apply_btn = QPushButton(t("set.hosts_apply"))
        apply_btn.clicked.connect(self._apply_hosts)
        manage_btn = QPushButton(t("set.hosts_manage"))
        manage_btn.clicked.connect(self._manage_blocked_domains)
        row.addWidget(self.hosts_check)
        row.addStretch(1)
        row.addWidget(apply_btn)
        row.addWidget(manage_btn)
        box.addLayout(row)

        hint = QLabel(t("set.hosts_admin"))
        hint.setObjectName("statusLabel")
        box.addWidget(hint)

    def _apply_hosts(self):
        from duai.core.system_clean import set_hosts_block
        try:
            set_hosts_block(self.hosts_check.isChecked())
            QMessageBox.information(self, "duAI", t("set.hosts_done"))
        except PermissionError:
            QMessageBox.warning(self, "duAI", t("set.hosts_perms"))

    def _manage_blocked_domains(self):
        from duai.core.system_clean import (
            get_blocked_domains, add_blocked_domain, remove_blocked_domain, set_hosts_block,
        )

        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("set.hosts_manage_title"))
        dialog.setText(t("set.hosts_manage_desc"))

        domains = get_blocked_domains()
        domains_text = "\n".join(f"• {d}" for d in domains)
        dialog.setDetailedText(domains_text)

        add_btn = dialog.addButton(t("set.hosts_add"), QMessageBox.ButtonRole.ActionRole)
        remove_btn = dialog.addButton(t("set.hosts_remove"), QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Close)

        dialog.exec()

        if dialog.clickedButton() == add_btn:
            domain, ok = QInputDialog.getText(self, t("set.hosts_add"), t("set.hosts_domain_prompt"))
            if ok and domain:
                add_blocked_domain(domain.strip())
                set_hosts_block(True)
                QMessageBox.information(self, "duAI", t("set.hosts_added", domain=domain))
        elif dialog.clickedButton() == remove_btn:
            domain, ok = QInputDialog.getText(self, t("set.hosts_remove"), t("set.hosts_domain_prompt"))
            if ok and domain:
                remove_blocked_domain(domain.strip())
                set_hosts_block(True)
                QMessageBox.information(self, "duAI", t("set.hosts_removed", domain=domain))

    # ---------- auto clean ----------
    def _build_auto_clean(self, layout):
        box = self._section(layout, t("set.autoclean_section"))

        service = get_auto_clean_service()
        cfg = service.load_config()

        self.ac_enabled = QCheckBox(t("set.autoclean_enable"))
        self.ac_enabled.setChecked(bool(cfg.get("enabled")))
        self.ac_enabled.toggled.connect(self._on_autoclean_changed)
        box.addWidget(self.ac_enabled)

        # Idle threshold
        row = QHBoxLayout()
        lbl = QLabel(t("set.autoclean_idle"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)

        self.ac_idle = QSpinBox()
        self.ac_idle.setRange(60, 3600)
        self.ac_idle.setSingleStep(60)
        self.ac_idle.setSuffix(" " + t("set.seconds"))
        self.ac_idle.setValue(int(cfg.get("idle_threshold", 300)))
        self.ac_idle.valueChanged.connect(self._on_autoclean_changed)
        row.addWidget(self.ac_idle)
        row.addStretch(1)
        box.addLayout(row)

        # Time interval
        row = QHBoxLayout()
        lbl = QLabel(t("set.autoclean_interval"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)

        self.ac_interval = QSpinBox()
        self.ac_interval.setRange(300, 86400)
        self.ac_interval.setSingleStep(300)
        self.ac_interval.setSuffix(" " + t("set.seconds"))
        self.ac_interval.setValue(int(cfg.get("time_interval", 3600)))
        self.ac_interval.valueChanged.connect(self._on_autoclean_changed)
        row.addWidget(self.ac_interval)
        row.addStretch(1)
        box.addLayout(row)

        # Clean mode
        row = QHBoxLayout()
        lbl = QLabel(t("set.autoclean_mode"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)

        self.ac_mode = QComboBox()
        self.ac_mode.addItems(["recycle", "permanent", "quarantine"])
        self.ac_mode.setCurrentText(cfg.get("mode", "recycle"))
        self.ac_mode.currentTextChanged.connect(self._on_autoclean_changed)
        row.addWidget(self.ac_mode)
        row.addStretch(1)
        box.addLayout(row)

        # Min freed threshold
        row = QHBoxLayout()
        lbl = QLabel(t("set.autoclean_min"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)

        self.ac_min = QSpinBox()
        self.ac_min.setRange(0, 1000)
        self.ac_min.setSuffix(" MB")
        self.ac_min.setValue(int(cfg.get("min_freed_mb", 1)))
        self.ac_min.valueChanged.connect(self._on_autoclean_changed)
        row.addWidget(self.ac_min)
        row.addStretch(1)
        box.addLayout(row)

        # Force clean button
        force_btn = QPushButton(t("set.autoclean_force"))
        force_btn.clicked.connect(self._force_autoclean)
        box.addWidget(force_btn)

        # Nota: al cambiar la configuracion se reinicia el servicio
        self._service = service

    def _on_autoclean_changed(self):
        service = get_auto_clean_service()
        was_running = bool(getattr(service, "_thread", None) and service._thread.is_alive())
        service.configure(
            enabled=self.ac_enabled.isChecked(),
            idle_threshold=self.ac_idle.value(),
            time_interval=self.ac_interval.value(),
            clean_mode=self.ac_mode.currentText(),
            min_freed_mb=self.ac_min.value(),
        )
        # Reiniciar el servicio para que aplique la nueva configuracion
        if was_running:
            try:
                service.stop()
                service.start()
            except Exception:
                pass

    def _force_autoclean(self):
        result = get_auto_clean_service().force_clean()
        if not result.get("ok"):
            QMessageBox.warning(self, "duAI", t("set.autoclean_error", error=result.get("error", "?")))
        else:
            freed_mb = result.get("freed_bytes", 0) / (1024 * 1024)
            QMessageBox.information(
                self, "duAI",
                t("set.autoclean_done", freed=f"{freed_mb:.1f}", items=result.get("removed_items", 0)),
            )

    # ---------- datos ----------
    def _build_data_controls(self, layout):
        box = self._section(layout, t("set.data_section"))

        # Export config
        export_btn = QPushButton(t("set.logs_export"))
        export_btn.clicked.connect(self._export_config)
        box.addWidget(export_btn)

        # Import config
        import_btn = QPushButton(t("set.logs_import"))
        import_btn.clicked.connect(self._import_config)
        box.addWidget(import_btn)

        # Reset all settings
        reset_btn = QPushButton(t("set.reset_all"))
        reset_btn.setObjectName("dangerBtn")
        reset_btn.clicked.connect(self._reset_all_settings)
        box.addWidget(reset_btn)

    def _export_config(self):
        import json
        path, _ = QFileDialog.getSaveFileName(self, t("set.logs_save_title"), "duai_config.json", "JSON (*.json)")
        if not path:
            return
        data = getattr(get_settings(), "_data", {})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {k: v for k, v in data.items() if k != "password_hash"},
                fh, indent=2, ensure_ascii=False,
            )
        QMessageBox.information(self, "duAI", t("set.export_done"))

    def _import_config(self):
        import json
        path, _ = QFileDialog.getOpenFileName(self, t("set.logs_load_title"), "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            settings = get_settings()
            settings._data.update(data)
            settings.save()
            QMessageBox.information(self, "duAI", t("set.import_done"))
            self.mw.refresh_settings_page()
        except Exception as e:
            QMessageBox.warning(self, "duAI", t("set.import_error", error=str(e)))

    def _reset_all_settings(self):
        confirm = QMessageBox.question(
            self, "duAI", t("set.reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from duai.utils.settings import reset_settings
        reset_settings()
        QMessageBox.information(self, "duAI", t("set.reset_done"))
        self.mw.refresh_settings_page()
