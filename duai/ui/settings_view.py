from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.system_clean import hosts_block_active, set_hosts_block
from ..security import auth
from ..utils.logger import open_logs_folder
from ..i18n import t
from ..utils.settings import get_settings


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

        self._build_language(layout)
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

    def _build_language(self, layout):
        box = self._section(layout, t("lang.section"))
        row = QHBoxLayout()
        lbl = QLabel(t("lang.section").upper())
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Espanol", "English"])
        current = get_settings().get("language") or "es"
        self.lang_combo.setCurrentIndex(1 if current == "en" else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self.lang_combo)
        box.addLayout(row)

    def _on_language_changed(self, index):
        from ..i18n import set_language
        lang = "en" if index == 1 else "es"
        set_language(lang)
        QMessageBox.information(self, "duAI", t("app.theme_applied", mode=lang.upper()))

    def _build_password(self, layout):
        box = self._section(layout, t("set.pwd_section"))
        note = QLabel(
            t("set.pwd_active")
            if auth.has_password()
            else t("set.pwd_none")
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

    def _clear_password(self):
        if not auth.has_password():
            return
        auth.clear_password()
        QMessageBox.information(self, "duAI", t("set.pwd_removed"))

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

    def _build_stealth(self, layout):
        box = self._section(layout, t("set.stealth_section"))
        self.purge_check = QCheckBox(t("set.stealth_check"))
        self.purge_check.setChecked(bool(get_settings().get("self_purge_on_exit")))
        self.purge_check.toggled.connect(
            lambda state: get_settings().set("self_purge_on_exit", bool(state))
        )
        box.addWidget(self.purge_check)
        hint = QLabel(
            t("set.stealth_hint")
        )
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)
        row = QHBoxLayout()
        wipe_btn = QPushButton(t("set.self_destruct"))
        wipe_btn.clicked.connect(self._wipe_own_data)
        row.addWidget(wipe_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _wipe_own_data(self):
        confirm = QMessageBox.question(
            self,
            "duAI",
            t("set.self_destruct_msg"),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from ..core.selfclean import purge_all_local_data

        purge_all_local_data()
        QMessageBox.information(self, "duAI", t("set.data_deleted"))
        self.mw.close()

    def _build_quarantine(self, layout):
        from ..core.quarantine import quarantined_items

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
        row.addWidget(restore_btn)
        row.addWidget(purge_btn)
        row.addStretch(1)
        box.addLayout(row)

    def _build_float_widget(self, layout):
        box = self._section(layout, t("set.float_section"))
        self.float_check = QCheckBox(t("set.float_check"))
        self.float_check.setChecked(bool(get_settings().get("float_visible")))
        self.float_check.toggled.connect(self._toggle_float)
        box.addWidget(self.float_check)
        hint = QLabel(
            t("set.float_hint")
        )
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

        box = self._section(layout, t("set.uninstall_section"))
        warning = QLabel(
            t("set.uninstall_warn")
        )
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
            self,
            "duAI",
            t("set.uninstall_confirm", names=names),
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

    def _restore_quarantine(self):
        from ..core.quarantine import restore_all

        restored = restore_all()
        QMessageBox.information(self, "duAI", t("set.quarantine_restored", count=restored))
        self.mw.refresh_settings_page()

    def _purge_quarantine(self):
        from ..core.quarantine import purge_quarantine

        removed = purge_quarantine()
        QMessageBox.information(self, "duAI", t("set.quarantine_emptied", count=removed))
        self.mw.refresh_settings_page()

    def _build_hosts(self, layout):
        box = self._section(layout, t("set.hosts_section"))
        self.hosts_check = QCheckBox(t("set.hosts_check"))
        self.hosts_check.setChecked(hosts_block_active())
        apply_btn = QPushButton(t("set.hosts_apply"))
        apply_btn.clicked.connect(self._apply_hosts)
        row = QHBoxLayout()
        row.addWidget(self.hosts_check)
        row.addStretch(1)
        row.addWidget(apply_btn)
        box.addLayout(row)
        hint = QLabel(t("set.hosts_admin"))
        hint.setObjectName("statusLabel")
        box.addWidget(hint)

    def _apply_hosts(self):
        try:
            set_hosts_block(self.hosts_check.isChecked())
            QMessageBox.information(self, "duAI", t("set.hosts_done"))
        except PermissionError:
            QMessageBox.warning(
                self, "duAI",
                t("set.hosts_perms"),
            )

    def _build_scheduler(self, layout):
        box = self._section(layout, t("set.scheduler_section"))
        from ..core.scheduler import logon_task_exists

        exists = logon_task_exists()
        state = QLabel(
            t("set.scheduler_active")
            if exists
            else t("set.scheduler_none")
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

    def _create_task(self):
        from ..core.scheduler import create_logon_task

        if create_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_created"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_create_fail"))

    def _remove_task(self):
        from ..core.scheduler import remove_logon_task

        if remove_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_deleted"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_delete_fail"))

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
