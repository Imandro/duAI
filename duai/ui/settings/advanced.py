"""Pestaña Avanzado de ajustes (widget flotante, programador, teclas, red).

Extraido de duai/ui/settings_view.py. API: AdvancedTab(main_window) -> QWidget
con atributo .scroll (QScrollArea).
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QFrame,
)

from duai.core.scheduler import create_logon_task, get_scheduler, logon_task_exists, remove_logon_task
from duai.core.uninstaller import find_installed_ai_apps
from duai.i18n import t
from duai.utils.settings import get_settings
from .base import SettingsTab


class AdvancedTab(SettingsTab):
    """Pestaña Avanzado."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_float_widget(layout)
        self._build_scheduler(layout)
        self._build_hotkeys(layout)
        self._build_network(layout)
        layout.addStretch(1)

    # ---------- widget flotante ----------
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

    # ---------- programador ----------
    def _build_scheduler(self, layout):
        box = self._section(layout, t("set.scheduler_section"))

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
        if create_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_created"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_create_fail"))
        self.mw.refresh_settings_page()

    def _remove_task(self):
        if remove_logon_task():
            QMessageBox.information(self, "duAI", t("set.scheduler_deleted"))
        else:
            QMessageBox.warning(self, "duAI", t("set.scheduler_delete_fail"))
        self.mw.refresh_settings_page()

    # ---------- teclas ----------
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

    # ---------- red ----------
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
