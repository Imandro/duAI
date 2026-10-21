"""Pestaña General de ajustes (idioma, arranque, contrasena, exclusiones).

Extraido de duai/ui/settings_view.py. API: GeneralTab(main_window) -> QWidget
con atributo .scroll (QScrollArea) listo para anadir a un QTabWidget.
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QFrame,
)

from duai.security import auth
from duai.i18n import t, set_language
from duai.utils.settings import get_settings
from .base import SettingsTab


class GeneralTab(SettingsTab):
    """Pestaña General."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_language(layout)
        self._build_startup(layout)
        self._build_password(layout)
        self._build_exclusions(layout)
        layout.addStretch(1)

    # ---------- idioma ----------
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

    # ---------- arranque ----------
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

    # ---------- contrasena ----------
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

    # ---------- exclusiones ----------
    def _build_exclusions(self, layout):
        box = self._section(layout, t("set.excl_section"))
        from duai.core.targets import list_all_entries

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
