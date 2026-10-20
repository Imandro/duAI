"""Settings view with theme, accent, high contrast, auto-clean, leaderboard, and more."""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QFrame,
    QSpinBox, QVBoxLayout, QWidget, QGroupBox, QSlider, QTabWidget
)
from PySide6.QtCore import Qt

from ..core.system_clean import hosts_block_active, set_hosts_block
from ..security import auth
from ..utils.logger import open_logs_folder
from ..i18n import t, set_language
from ..utils.settings import get_settings
from ..core.viral import set_gamification
from ..core.leaderboard import is_leaderboard_enabled, set_leaderboard_enabled
from ..core.auto_clean import get_auto_clean_service
from ..core.scheduler import get_scheduler
from ..core.quarantine import quarantined_items, restore_all, purge_quarantine
from ..core.uninstaller import find_installed_ai_apps
from ..core.leaderboard import get_user_rank
from .theme import current_mode, apply_theme, AVAILABLE_ACCENTS, AVAILABLE_THEMES
from PySide6.QtWidgets import QApplication


class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("set.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)
        title = QLabel(t("set.subtitle"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; color: #FFFFFF;")
        outer.addWidget(title)

        # Tab widget for organized settings
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        outer.addWidget(self.tabs, 1)

        # Build tabs
        self._build_general_tab()
        self._build_appearance_tab()
        self._build_privacy_tab()
        self._build_viral_tab()
        self._build_advanced_tab()
        self._build_maintenance_tab()

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

    def _create_scroll_content(self):
        """Create a scrollable content widget."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(24)
        scroll.setWidget(content)
        return scroll, layout

    # ==================== GENERAL TAB ====================
    def _build_general_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_general"))

        self._build_language(layout)
        self._build_startup(layout)
        self._build_password(layout)
        self._build_exclusions(layout)
        layout.addStretch(1)

    def _build_language(self, layout):
        box = self._section(layout, t("lang.section"))
        row = QHBoxLayout()
        lbl = QLabel(t("lang.current"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Español", "English"])
        current = get_settings().get("language") or "es"
        self.lang_combo.setCurrentIndex(1 if current == "en" else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self.lang_combo)
        row.addStretch(1)
        box.addLayout(row)

    def _on_language_changed(self, index):
        lang = "en" if index == 1 else "es"
        set_language(lang)
        QMessageBox.information(self, "duAI", t("app.theme_applied", mode=lang.upper()))
        self.mw.refresh_ui_text()

    def _build_startup(self, layout):
        box = self._section(layout, t("set.startup_section"))
        
        self.startup_check = QCheckBox(t("set.startup_check"))
        self.startup_check.setChecked(get_settings().get("check_updates", True))
        self.startup_check.toggled.connect(
            lambda state: get_settings().set("check_updates", bool(state))
        )
        box.addWidget(self.startup_check)
        
        self.minimize_check = QCheckBox(t("set.startup_minimized"))
        self.minimize_check.setChecked(get_settings().get("start_minimized", False))
        self.minimize_check.toggled.connect(
            lambda state: get_settings().set("start_minimized", bool(state))
        )
        box.addWidget(self.minimize_check)
        
        self.tray_check = QCheckBox(t("set.minimize_to_tray"))
        self.tray_check.setChecked(get_settings().get("minimize_to_tray", True))
        self.tray_check.toggled.connect(
            lambda state: get_settings().set("minimize_to_tray", bool(state))
        )
        box.addWidget(self.tray_check)

    def _build_password(self, layout):
        box = self._section(layout, t("set.pwd_section"))
        note = QLabel(
            t("set.pwd_active") if auth.has_password() else t("set.pwd_none")
        )
        note.setObjectName("heroBody")
        note.setWordWrap(True)
        box.addWidget(note)

        row = QHBoxLayout()
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText(t("set.pwd_new"))
        self.pw_confirm = QLineEdit()
        self.pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_confirm.setPlaceholderText(t("set.pwd_confirm"))
        set_btn = QPushButton(t("set.pwd_set"))
        set_btn.clicked.connect(self._set_password)
        clear_btn = QPushButton(t("set.pwd_remove"))
        clear_btn.clicked.connect(self._clear_password)
        for widget in (self.pw_input, self.pw_confirm, set_btn, clear_btn):
            row.addWidget(widget)
        box.addLayout(row)

    def _set_password(self):
        pw = self.pw_input.text()
        if len(pw) < 4:
            QMessageBox.information(self, "duAI", t("set.pwd_min"))
            return
        if pw != self.pw_confirm.text():
            QMessageBox.information(self, "duAI", t("set.pwd_mismatch"))
            return
        auth.set_password(pw)
        self.pw_input.clear()
        self.pw_confirm.clear()
        QMessageBox.information(self, "duAI", t("set.pwd_done"))
        self.mw.refresh_settings_page()

    def _clear_password(self):
        if not auth.has_password():
            return
        auth.clear_password()
        QMessageBox.information(self, "duAI", t("set.pwd_removed"))
        self.mw.refresh_settings_page()

    def _build_exclusions(self, layout):
        box = self._section(layout, t("set.excl_section"))
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

    # ==================== APPEARANCE TAB ====================
    def _build_appearance_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_appearance"))

        self._build_theme_selector(layout)
        self._build_accent_selector(layout)
        self._build_high_contrast(layout)
        self._build_font_scaling(layout)
        self._build_animations(layout)
        layout.addStretch(1)

    def _build_theme_selector(self, layout):
        box = self._section(layout, t("set.theme_section"))
        
        row = QHBoxLayout()
        lbl = QLabel(t("set.theme_mode"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        
        self.theme_combo = QComboBox()
        for theme_id, theme_name in AVAILABLE_THEMES.items():
            self.theme_combo.addItem(theme_name, theme_id)
        
        current = current_mode()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current:
                self.theme_combo.setCurrentIndex(i)
                break
        
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row.addWidget(self.theme_combo)
        row.addStretch(1)
        box.addLayout(row)
        
        # Auto-detect system theme
        self.auto_theme_check = QCheckBox(t("set.theme_auto"))
        self.auto_theme_check.setChecked(get_settings().get("theme.auto_detect", True))
        self.auto_theme_check.toggled.connect(
            lambda state: get_settings().set("theme.auto_detect", bool(state))
        )
        box.addWidget(self.auto_theme_check)

    def _on_theme_changed(self, index):
        theme_id = self.theme_combo.itemData(index)
        apply_theme(QApplication.instance(), theme_id, get_settings().get("accent_color", ""))
        get_settings().set("theme.mode", theme_id)
        get_settings().save()
        self.mw.apply_theme()

    def _build_accent_selector(self, layout):
        box = self._section(layout, t("set.accent_section"))
        
        row = QHBoxLayout()
        lbl = QLabel(t("viral.accent"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        
        self.acc_combo = QComboBox()
        self.acc_combo.addItem(t("viral.accent_none"), "")
        for accent_id, accent_name in AVAILABLE_ACCENTS.items():
            self.acc_combo.addItem(accent_name, accent_id)
        
        current = get_settings().get("accent_color") or ""
        for i in range(self.acc_combo.count()):
            if self.acc_combo.itemData(i) == current:
                self.acc_combo.setCurrentIndex(i)
                break
        
        self.acc_combo.currentIndexChanged.connect(self._on_accent_changed)
        row.addWidget(self.acc_combo)
        row.addStretch(1)
        box.addLayout(row)

    def _on_accent_changed(self, index):
        accent_id = self.acc_combo.itemData(index)
        apply_theme(QApplication.instance(), current_mode(), accent_id)
        get_settings().set("accent_color", accent_id)
        get_settings().save()
        self.mw.apply_accent_mode(accent_id)

    def _build_high_contrast(self, layout):
        box = self._section(layout, t("set.contrast_section"))
        
        self.hc_check = QCheckBox(t("set.high_contrast"))
        self.hc_check.setChecked(get_settings().get("theme.high_contrast", False))
        self.hc_check.toggled.connect(self._on_high_contrast_changed)
        box.addWidget(self.hc_check)
        
        hint = QLabel(t("set.high_contrast_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

    def _on_high_contrast_changed(self, state):
        get_settings().set("theme.high_contrast", bool(state))
        get_settings().save()
        apply_theme(QApplication.instance(), current_mode(), get_settings().get("accent_color", ""))
        self.mw.apply_theme()

    def _build_font_scaling(self, layout):
        box = self._section(layout, t("set.font_section"))
        
        row = QHBoxLayout()
        lbl = QLabel(t("set.font_scale"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(80, 150)
        self.font_slider.setValue(int(get_settings().get("theme.font_scale", 1.0) * 100))
        self.font_slider.setTickInterval(10)
        self.font_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.font_slider.valueChanged.connect(self._on_font_scale_changed)
        row.addWidget(self.font_slider, 1)
        
        self.font_label = QLabel(f"{self.font_slider.value()}%")
        self.font_label.setObjectName("microLabel")
        self.font_label.setMinimumWidth(50)
        row.addWidget(self.font_label)
        box.addLayout(row)

    def _on_font_scale_changed(self, value):
        scale = value / 100.0
        self.font_label.setText(f"{value}%")
        get_settings().set("theme.font_scale", scale)
        get_settings().save()
        apply_theme(QApplication.instance(), current_mode(), get_settings().get("accent_color", ""))
        self.mw.apply_theme()

    def _build_animations(self, layout):
        box = self._section(layout, t("set.animations_section"))
        
        self.anim_check = QCheckBox(t("set.animations_enable"))
        self.anim_check.setChecked(get_settings().get("theme.animations", True))
        self.anim_check.toggled.connect(
            lambda state: get_settings().set("theme.animations", bool(state))
        )
        box.addWidget(self.anim_check)
        
        self.reduced_motion_check = QCheckBox(t("set.reduced_motion"))
        self.reduced_motion_check.setChecked(get_settings().get("theme.reduced_motion", False))
        self.reduced_motion_check.toggled.connect(
            lambda state: get_settings().set("theme.reduced_motion", bool(state))
        )
        box.addWidget(self.reduced_motion_check)

    # ==================== PRIVACY TAB ====================
    def _build_privacy_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_privacy"))

        self._build_stealth(layout)
        self._build_hosts(layout)
        self._build_auto_clean(layout)
        self._build_data_controls(layout)
        layout.addStretch(1)

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
        from ..core.selfclean import purge_all_local_data
        result = purge_all_local_data()
        if result.get("success"):
            QMessageBox.information(self, "duAI", t("set.data_deleted"))
        else:
            QMessageBox.warning(self, "duAI", t("set.data_deleted_partial", errors="; ".join(result.get("errors", []))))
        self.mw.close()

    def _build_hosts(self, layout):
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
        try:
            set_hosts_block(self.hosts_check.isChecked())
            QMessageBox.information(self, "duAI", t("set.hosts_done"))
        except PermissionError:
            QMessageBox.warning(self, "duAI", t("set.hosts_perms"))

    def _manage_blocked_domains(self):
        from ..core.system_clean import get_blocked_domains, add_blocked_domain, remove_blocked_domain, set_hosts_block
        
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
            # Simple input dialog
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
        path, _ = QFileDialog.getOpenFileName(self, t("set.logs_load_title"), "", "JSON (*.json)")
        if not path:
            return
        try:
            import json
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
        from ..utils.settings import reset_settings
        reset_settings()
        QMessageBox.information(self, "duAI", t("set.reset_done"))
        self.mw.refresh_settings_page()

    # ==================== VIRAL TAB ====================
    def _build_viral_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_viral"))

        self._build_gamification(layout)
        self._build_leaderboard(layout)
        self._build_sharing(layout)
        self._build_challenges(layout)
        layout.addStretch(1)

    def _build_gamification(self, layout):
        box = self._section(layout, t("viral.gamification"))
        
        self.gam_check = QCheckBox(t("viral.stats"))
        self.gam_check.setChecked(bool(get_settings().get("gamification", True)))
        self.gam_check.toggled.connect(
            lambda state: set_gamification(bool(state))
        )
        box.addWidget(self.gam_check)
        
        hint = QLabel(t("viral.gamification_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)
        
        # Reset stats
        reset_btn = QPushButton(t("viral.reset_stats"))
        reset_btn.clicked.connect(self._reset_stats)
        box.addWidget(reset_btn)

    def _reset_stats(self):
        confirm = QMessageBox.question(
            self, "duAI", t("viral.reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            from ..core.viral import reset_stats
            reset_stats()
            QMessageBox.information(self, "duAI", t("viral.reset_done"))
            self.mw.refresh_settings_page()

    def _build_leaderboard(self, layout):
        box = self._section(layout, t("viral.leaderboard"))
        
        enabled = is_leaderboard_enabled()
        self.lb_check = QCheckBox(t("viral.leaderboard_enable"))
        self.lb_check.setChecked(enabled)
        self.lb_check.toggled.connect(lambda state: set_leaderboard_enabled(bool(state)))
        box.addWidget(self.lb_check)
        
        # Show current rank
        if enabled:
            rank_info = get_user_rank()
            rank_text = t("viral.your_rank", rank=rank_info['rank'], total=rank_info['total'], 
                         percentile=rank_info['percentile'], tier=rank_info['tier'].capitalize())
            rank_label = QLabel(rank_text)
            rank_label.setObjectName("heroBody")
            rank_label.setWordWrap(True)
            box.addWidget(rank_label)
            
            refresh_btn = QPushButton(t("viral.refresh_rank"))
            refresh_btn.clicked.connect(lambda: self.mw.refresh_settings_page())
            box.addWidget(refresh_btn)
        
        hint = QLabel(t("viral.leaderboard_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

    def _build_sharing(self, layout):
        box = self._section(layout, t("viral.sharing"))
        
        # Default share platform
        row = QHBoxLayout()
        lbl = QLabel(t("viral.default_platform"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        
        self.share_combo = QComboBox()
        self.share_combo.addItems(["Twitter/X", "LinkedIn", "Mastodon", "Bluesky", "Reddit", "Email"])
        current = get_settings().get("share_platform") or "twitter"
        self.share_combo.setCurrentText(current.capitalize())
        self.share_combo.currentIndexChanged.connect(self._on_share_changed)
        row.addWidget(self.share_combo)
        row.addStretch(1)
        box.addLayout(row)
        
        # Auto-share after clean
        self.auto_share_check = QCheckBox(t("viral.auto_share"))
        self.auto_share_check.setChecked(get_settings().get("viral.auto_share", False))
        self.auto_share_check.toggled.connect(
            lambda state: get_settings().set("viral.auto_share", bool(state))
        )
        box.addWidget(self.auto_share_check)

    def _on_share_changed(self, index):
        platform = self.share_combo.currentText().lower()
        get_settings().set("share_platform", platform)

    def _build_challenges(self, layout):
        box = self._section(layout, t("viral.challenges"))
        
        self.challenge_check = QCheckBox(t("viral.challenges_enable"))
        self.challenge_check.setChecked(get_settings().get("viral.challenges", True))
        self.challenge_check.toggled.connect(
            lambda state: get_settings().set("viral.challenges", bool(state))
        )
        box.addWidget(self.challenge_check)
        
        hint = QLabel(t("viral.challenges_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

    # ==================== ADVANCED TAB ====================
    def _build_advanced_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_advanced"))

        self._build_float_widget(layout)
        self._build_scheduler(layout)
        self._build_hotkeys(layout)
        self._build_network(layout)
        layout.addStretch(1)

    def _build_float_widget(self, layout):
        box = self._section(layout, t("set.float_section"))
        
        self.float_check = QCheckBox(t("set.float_check"))
        self.float_check.setChecked(bool(get_settings().get("float_visible")))
        self.float_check.toggled.connect(self._toggle_float)
        box.addWidget(self.float_check)
        
        hint = QLabel(t("set.float_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)
        
        size_row = QHBoxLayout()
        size_label = QLabel(t("set.float_size"))
        size_label.setObjectName("microLabel")
        size_row.addWidget(size_label)
        self.float_size = QSpinBox()
        self.float_size.setRange(80, 300)
        self.float_size.setSingleStep(10)
        current = get_settings().get("float_size") or 160
        self.float_size.setValue(current)
        self.float_size.setSuffix(" px")
        self.float_size.valueChanged.connect(self._change_float_size)
        size_row.addWidget(self.float_size)
        size_row.addStretch(1)
        box.addLayout(size_row)
        
        # Position
        pos_row = QHBoxLayout()
        pos_label = QLabel(t("set.float_position"))
        pos_label.setObjectName("microLabel")
        pos_row.addWidget(pos_label)
        self.float_pos = QComboBox()
        self.float_pos.addItems(["bottom-right", "bottom-left", "top-right", "top-left"])
        self.float_pos.setCurrentText(get_settings().get("float_position", "bottom-right"))
        self.float_pos.currentTextChanged.connect(
            lambda v: get_settings().set("float_position", v)
        )
        pos_row.addWidget(self.float_pos)
        pos_row.addStretch(1)
        box.addLayout(pos_row)

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

    def _build_scheduler(self, layout):
        box = self._section(layout, t("set.scheduler_section"))
        from ..core.scheduler import logon_task_exists
        
        exists = logon_task_exists()
        state = QLabel(
            t("set.scheduler_active") if exists else t("set.scheduler_none")
        )
        state.setObjectName("heroBody")
        box.addWidget(state)
        
        row = QHBoxLayout()
        create_btn = QPushButton(t("set.scheduler_create"))
        create_btn.clicked.connect(self._create_task)
        remove_btn = QPushButton(t("set.scheduler_delete"))
        remove_btn.clicked.connect(self._remove_task)
        row.addWidget(create_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        box.addLayout(row)
        
        # Advanced scheduler settings
        self.adv_sched_check = QCheckBox(t("set.scheduler_advanced"))
        self.adv_sched_check.setChecked(get_settings().get("scheduler.advanced", False))
        self.adv_sched_check.toggled.connect(
            lambda state: get_settings().set("scheduler.advanced", bool(state))
        )
        box.addWidget(self.adv_sched_check)

    def _create_task(self):
        from ..core.scheduler import create_logon_task
        if create_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_created"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_create_fail"))
        self.mw.refresh_settings_page()

    def _remove_task(self):
        from ..core.scheduler import remove_logon_task
        if remove_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_deleted"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_delete_fail"))
        self.mw.refresh_settings_page()

    def _build_hotkeys(self, layout):
        box = self._section(layout, t("set.hotkeys_section"))
        
        self.hotkey_check = QCheckBox(t("set.hotkey_enable"))
        self.hotkey_check.setChecked(get_settings().get("hotkey_enabled", False))
        self.hotkey_check.toggled.connect(
            lambda state: get_settings().set("hotkey_enabled", bool(state))
        )
        box.addWidget(self.hotkey_check)
        
        # Hotkey combination
        row = QHBoxLayout()
        lbl = QLabel(t("set.hotkey_combo"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems([
            "Ctrl+Shift+P", "Ctrl+Alt+P", "Ctrl+Shift+X", 
            "Ctrl+Alt+X", "Win+P", "Win+X"
        ])
        current = get_settings().get("hotkey_combo", "Ctrl+Shift+P")
        self.hotkey_combo.setCurrentText(current)
        self.hotkey_combo.currentTextChanged.connect(
            lambda v: get_settings().set("hotkey_combo", v)
        )
        row.addWidget(self.hotkey_combo)
        row.addStretch(1)
        box.addLayout(row)
        
        hint = QLabel(t("set.hotkey_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

    def _build_network(self, layout):
        box = self._section(layout, t("set.network_section"))
        
        self.proxy_check = QCheckBox(t("set.proxy_enable"))
        self.proxy_check.setChecked(get_settings().get("proxy.enabled", False))
        self.proxy_check.toggled.connect(
            lambda state: get_settings().set("proxy.enabled", bool(state))
        )
        box.addWidget(self.proxy_check)
        
        # Proxy settings
        row = QHBoxLayout()
        lbl = QLabel(t("set.proxy_address"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("host:port")
        self.proxy_host.setText(get_settings().get("proxy.host", ""))
        self.proxy_host.textChanged.connect(
            lambda v: get_settings().set("proxy.host", v)
        )
        row.addWidget(self.proxy_host)
        box.addLayout(row)

    # ==================== MAINTENANCE TAB ====================
    def _build_maintenance_tab(self):
        scroll, layout = self._create_scroll_content()
        self.tabs.addTab(scroll, t("set.tab_maintenance"))

        self._build_quarantine(layout)
        self._build_uninstall(layout)
        self._build_logs(layout)
        self._build_diagnostics(layout)
        layout.addStretch(1)

    def _build_quarantine(self, layout):
        box = self._section(layout, t("set.quarantine_section"))
        
        items = quarantined_items()
        count_label = QLabel(t("set.quarantine_count", count=len(items)))
        count_label.setObjectName("heroBody")
        box.addWidget(count_label)
        
        row = QHBoxLayout()
        restore_btn = QPushButton(t("set.quarantine_restore"))
        restore_btn.clicked.connect(self._restore_quarantine)
        purge_btn = QPushButton(t("set.quarantine_empty"))
        purge_btn.clicked.connect(self._purge_quarantine)
        verify_btn = QPushButton(t("set.quarantine_verify"))
        verify_btn.clicked.connect(self._verify_quarantine)
        row.addWidget(restore_btn)
        row.addWidget(purge_btn)
        row.addWidget(verify_btn)
        row.addStretch(1)
        box.addLayout(row)
        
        # Auto-purge settings
        auto_purge = QCheckBox(t("set.quarantine_auto_purge"))
        auto_purge.setChecked(get_settings().get("quarantine.auto_purge", True))
        auto_purge.toggled.connect(
            lambda state: get_settings().set("quarantine.auto_purge", bool(state))
        )
        box.addWidget(auto_purge)
        
        row = QHBoxLayout()
        lbl = QLabel(t("set.quarantine_max_age"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        self.quarantine_age = QSpinBox()
        self.quarantine_age.setRange(1, 365)
        self.quarantine_age.setSuffix(" " + t("set.days"))
        self.quarantine_age.setValue(get_settings().get("quarantine.max_age", 30))
        self.quarantine_age.valueChanged.connect(
            lambda v: get_settings().set("quarantine.max_age", v)
        )
        row.addWidget(self.quarantine_age)
        row.addStretch(1)
        box.addLayout(row)

    def _restore_quarantine(self):
        restored = restore_all()
        QMessageBox.information(self, "duAI", t("set.quarantine_restored", count=restored))
        self.mw.refresh_settings_page()

    def _purge_quarantine(self):
        confirm = QMessageBox.question(
            self, "duAI", t("set.quarantine_empty_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            removed = purge_quarantine()
            QMessageBox.information(self, "duAI", t("set.quarantine_emptied", count=removed))
            self.mw.refresh_settings_page()

    def _verify_quarantine(self):
        from ..core.quarantine import verify_quarantine_integrity
        result = verify_quarantine_integrity()
        QMessageBox.information(self, "duAI", 
            t("set.quarantine_verified", ok=result.get("verified", result.get("valid", 0)), corrupted=result["corrupted"], missing=result["missing"]))

    def _build_uninstall(self, layout):
        box = self._section(layout, t("set.uninstall_section"))
        
        warning = QLabel(t("set.uninstall_warn"))
        warning.setObjectName("heroBody")
        warning.setWordWrap(True)
        box.addWidget(warning)

        try:
            self._apps = find_installed_ai_apps()
        except Exception:
            self._apps = []

        if not self._apps:
            empty = QLabel(t("set.no_apps"))
            empty.setObjectName("statusLabel")
            box.addWidget(empty)
            return

        self._uninstall_checks = {}
        for app in self._apps:
            quiet = t("set.silent") if app["quiet_string"] else t("set.assisted")
            check = QCheckBox(f"{app['name']}  ·  {quiet}")
            self._uninstall_checks[app["name"]] = check
            box.addWidget(check)

        row = QHBoxLayout()
        uninstall_btn = QPushButton(t("set.uninstall_btn"))
        uninstall_btn.setObjectName("dangerBtn")
        uninstall_btn.clicked.connect(self._uninstall_selected)
        refresh_btn = QPushButton(t("set.redetect"))
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
            QMessageBox.information(self, "duAI", t("set.select_app"))
            return
        names = "\n".join("· " + app["name"] for app in selected)
        confirm = QMessageBox.question(
            self, "duAI", t("set.uninstall_confirm", names=names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
                        extra = " " + t("set.traces_removed", count=cleaned.removed_items, bytes=cleaned.freed_bytes)
                    lines.append(f"{t('set.ok')} {name} ({detail}){extra}")
                else:
                    lines.append(f"{t('set.fail')} {name}: {detail}")
            QMessageBox.information(self, "duAI", "\n".join(lines))
            self.mw.refresh_settings_page()

        self.mw.run_cli_worker(job, done)

    def _build_logs(self, layout):
        box = self._section(layout, t("set.logs_section"))
        row = QHBoxLayout()
        open_btn = QPushButton(t("set.logs_open"))
        open_btn.clicked.connect(open_logs_folder)
        export_btn = QPushButton(t("set.logs_export"))
        export_btn.clicked.connect(self._export_config)
        row.addWidget(open_btn)
        row.addWidget(export_btn)
        row.addStretch(1)
        box.addLayout(row)
        
        # Log level
        row = QHBoxLayout()
        lbl = QLabel(t("set.log_level"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText(get_settings().get("log_level", "INFO"))
        self.log_level.currentTextChanged.connect(
            lambda v: get_settings().set("log_level", v)
        )
        row.addWidget(self.log_level)
        row.addStretch(1)
        box.addLayout(row)

    def _build_diagnostics(self, layout):
        box = self._section(layout, t("set.diagnostics_section"))
        
        # System info
        info_btn = QPushButton(t("set.diagnostics_info"))
        info_btn.clicked.connect(self._show_system_info)
        box.addWidget(info_btn)
        
        # Run self-test
        test_btn = QPushButton(t("set.diagnostics_test"))
        test_btn.clicked.connect(self._run_self_test)
        box.addWidget(test_btn)
        
        # Check for updates
        update_btn = QPushButton(t("updater.check"))
        update_btn.clicked.connect(lambda: self.mw.navigate(8))
        box.addWidget(update_btn)

    def _show_system_info(self):
        import platform
        import sys
        from ..utils.logger import base_dir
        
        info = f"""
duAI System Information
=======================
Version: 2.0.0
Python: {sys.version.split()[0]}
Platform: {platform.platform()}
Architecture: {platform.machine()}
Admin: {__import__('..utils.paths', fromlist=['is_admin']).is_admin()}
Base Dir: {base_dir()}
Theme: {current_mode()}
Accent: {get_settings().get('accent_color', 'none')}
Language: {get_settings().get('language', 'es')}
Gamification: {get_settings().get('gamification', True)}
Portable: {getattr(sys, 'frozen', False) and 'portable' in sys.argv}
        """
        QMessageBox.information(self, "duAI Diagnostics", info.strip())

    def _run_self_test(self):
        # Run basic self-tests
        tests = [
            ("Settings", self._test_settings),
            ("Scanner", self._test_scanner),
            ("Cleaner", self._test_cleaner),
            ("Quarantine", self._test_quarantine),
            ("Theme", self._test_theme),
        ]
        
        results = []
        for name, test_func in tests:
            try:
                test_func()
                results.append(f"✓ {name}: OK")
            except Exception as e:
                results.append(f"✗ {name}: {str(e)}")
        
        QMessageBox.information(self, "duAI", t("set.test_results", results="\n".join(results)))

    def _test_settings(self):
        s = get_settings()
        s.set("test_key", "test_value")
        assert s.get("test_key") == "test_value"
    
    def _test_scanner(self):
        from ..core.scanner import scan_targets
        from ..core.targets import build_targets
        targets = build_targets()
        report = scan_targets(targets[:1])  # Scan just one target
        assert report is not None
    
    def _test_cleaner(self):
        from ..core.cleaner import CleanOptions, run_clean
        from ..core.scanner import scan_targets
        from ..core.targets import build_targets
        targets = build_targets()
        report = scan_targets(targets[:1])
        options = CleanOptions(selected=set(), mode="recycle", preview=True)
        result = run_clean(report, options)
        assert result is not None
    
    def _test_quarantine(self):
        from ..core.quarantine import get_quarantine_stats
        stats = get_quarantine_stats()
        assert "total_items" in stats
    
    def _test_theme(self):
        from .theme import apply_theme
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), "oscuro", "")