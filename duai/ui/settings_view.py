"""Settings view - contenedor de las 6 pestañas de ajustes.

Refactor: la logica de cada pestaña vivo ahora en duai/ui/settings/ (uno por
pestaña). Esta clase solo ensambla las pestañas en un QTabWidget y mantiene
la API publica usada por el resto de la app (app.py, ui_test.py, demo_view).
"""

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from ..i18n import t
from .settings import (
    AppearanceTab, AdvancedTab, GeneralTab, MaintenanceTab,
    PrivacyTab, ViralTab,
)


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

        # Build tabs (orden: general, apariencia, privacidad, viral, avanzado, mantenimiento)
        self.tabs.addTab(GeneralTab(self.mw).scroll, t("set.tab_general"))
        self.tabs.addTab(AppearanceTab(self.mw).scroll, t("set.tab_appearance"))
        self.tabs.addTab(PrivacyTab(self.mw).scroll, t("set.tab_privacy"))
        self.tabs.addTab(ViralTab(self.mw).scroll, t("set.tab_viral"))
        self.tabs.addTab(AdvancedTab(self.mw).scroll, t("set.tab_advanced"))
        self.tabs.addTab(MaintenanceTab(self.mw).scroll, t("set.tab_maintenance"))
