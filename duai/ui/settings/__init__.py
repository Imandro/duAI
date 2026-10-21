"""Paquete de pestañas de ajustes de duAI.

Divide la antigua duai/ui/settings_view.py (6 pestañas, muy larga) en modulos
uno por pestaña:

- general.py   -> GeneralTab
- appearance.py -> AppearanceTab
- privacy.py   -> PrivacyTab
- viral.py     -> ViralTab
- advanced.py  -> AdvancedTab
- maintenance.py -> MaintenanceTab

Cada una hereda de SettingsTab (base.py) y expone un atributo .scroll
(QScrollArea) listo para anadir a un QTabWidget.

SettingsView (settings_view.py) mantiene la API publica usada por el resto
de la app: SettingsView(main_window) con .tabs (QTabWidget) y .mw.
"""

from .appearance import AppearanceTab
from .advanced import AdvancedTab
from .base import SettingsTab
from .general import GeneralTab
from .maintenance import MaintenanceTab
from .privacy import PrivacyTab
from .viral import ViralTab

__all__ = [
    "AppearanceTab",
    "AdvancedTab",
    "SettingsTab",
    "GeneralTab",
    "MaintenanceTab",
    "PrivacyTab",
    "ViralTab",
]
