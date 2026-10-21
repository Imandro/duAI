"""Pestaña Apariencia de ajustes (tema, acento, contraste, fuente, animaciones).

Extraido de duai/ui/settings_view.py. API: AppearanceTab(main_window) -> QWidget
con atributo .scroll (QScrollArea).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QFrame,
)

from duai.i18n import t
from duai.utils.settings import get_settings
from .base import SettingsTab
from duai.ui.theme import current_mode, apply_theme, AVAILABLE_ACCENTS, AVAILABLE_THEMES


class AppearanceTab(SettingsTab):
    """Pestaña Apariencia."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_theme_selector(layout)
        self._build_accent_selector(layout)
        self._build_high_contrast(layout)
        self._build_font_scaling(layout)
        self._build_animations(layout)
        layout.addStretch(1)

    # ---------- tema ----------
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

        # Auto-detectar tema del sistema
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

    # ---------- acento ----------
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

    # ---------- alto contraste ----------
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

    # ---------- escala de fuente ----------
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

    # ---------- animaciones ----------
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
