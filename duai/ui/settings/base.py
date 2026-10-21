"""Clase base y helpers compartidos de las pestañas de ajustes.

Extraido de duai/ui/settings_view.py durante la division de la vista
en modulos uno por pestaña. Toda pestaña hereda de SettingsTab para
reutilizar los helpers de seccion y area desplazable.
"""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


class SettingsTab(QWidget):
    """Clase base de una pestaña de ajustes.

    Almacena la referencia a la ventana principal y ofrece los helpers
    _section / _create_scroll_content usados por todas las pestañas.
    """

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

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
        """Crea un QScrollArea desplazable con su layout de contenido."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(24)
        scroll.setWidget(content)
        return scroll, layout
