"""Pestaña Mantenimiento de ajustes (cuarentena, desinstalador, logs, diagnosticos).

Extraido de duai/ui/settings_view.py. API: MaintenanceTab(main_window) -> QWidget
con atributo .scroll (QScrollArea).
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QFrame,
)

from duai.core.quarantine import (
    quarantined_items, restore_all, purge_quarantine, verify_quarantine_integrity,
)
from duai.core.uninstaller import clean_traces_for_app, find_installed_ai_apps, run_uninstall
from duai.i18n import t
from duai.ui.theme import current_mode
from duai.utils.logger import open_logs_folder
from duai.utils.settings import get_settings
from .base import SettingsTab


class MaintenanceTab(SettingsTab):
    """Pestaña Mantenimiento."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_quarantine(layout)
        self._build_uninstall(layout)
        self._build_logs(layout)
        self._build_diagnostics(layout)
        layout.addStretch(1)

    # ---------- cuarentena ----------
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
        result = verify_quarantine_integrity()
        QMessageBox.information(self, "duAI",
            t("set.quarantine_verified", ok=result.get("verified", result.get("valid", 0)), corrupted=result["corrupted"], missing=result["missing"]))

    # ---------- desinstalador ----------
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

        def job():
            results = []
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

    # ---------- logs ----------
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

    # ---------- datos (export/import/reset) ----------
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

    # ---------- diagnosticos ----------
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

    def _show_system_info(self):
        import platform
        import sys
        from duai.utils.logger import base_dir
        from duai.utils.paths import is_admin

        info = f"""
duAI System Information
=======================
Version: 2.0.0
Python: {sys.version.split()[0]}
Platform: {platform.platform()}
Architecture: {platform.machine()}
Admin: {is_admin()}
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
        from duai.core.scanner import scan_targets
        from duai.core.targets import build_targets
        targets = build_targets()
        report = scan_targets(targets[:1])  # Scan just one target
        assert report is not None

    def _test_cleaner(self):
        from duai.core.cleaner import CleanOptions, run_clean
        from duai.core.scanner import scan_targets
        from duai.core.targets import build_targets
        targets = build_targets()
        report = scan_targets(targets[:1])
        options = CleanOptions(selected=set(), mode="recycle", preview=True)
        result = run_clean(report, options)
        assert result is not None

    def _test_quarantine(self):
        from duai.core.quarantine import get_quarantine_stats
        stats = get_quarantine_stats()
        assert "total_items" in stats

    def _test_theme(self):
        from duai.ui.theme import apply_theme
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), "oscuro", "")
