from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.paths import fmt_bytes
from .animations import count_to


class DashboardView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(14)

        layout.addWidget(self._micro("ESTADO"))
        title = QLabel("Privacidad absoluta.")
        title.setObjectName("heroTitle")
        layout.addWidget(title)

        body = QLabel(
            "duAI detecta y elimina los rastros que las herramientas de inteligencia "
            "artificial dejan en tu equipo: aplicaciones, navegadores, registro, DNS, "
            "portapapeles y cronologia. Todo se procesa localmente. Nada sale de tu computadora."
        )
        body.setObjectName("heroBody")
        body.setWordWrap(True)
        body.setMaximumWidth(560)
        layout.addWidget(body)
        layout.addSpacing(24)

        self.stats_frame = QFrame()
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(48)

        self.stat_traces = self._stat(stats_layout, "RASTROS DETECTADOS", "0")
        self.stat_size = self._stat(stats_layout, "ESPACIO EN RIESGO", "0 B")
        self.stat_freed = self._stat(stats_layout, "LIBERADO ESTA SESION", "0 B")
        self.stat_last = self._stat(stats_layout, "ULTIMO ESCANEO", "NUNCA")
        layout.addWidget(self.stats_frame)

        layout.addSpacing(16)
        buttons = QHBoxLayout()
        scan_btn = QPushButton("INICIAR ESCANEO")
        scan_btn.clicked.connect(self._go_scan)
        clean_btn = QPushButton("IR A LIMPIEZA")
        clean_btn.clicked.connect(lambda: self.mw.navigate(2))
        buttons.addWidget(scan_btn)
        buttons.addWidget(clean_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)

        footer = QLabel("SIN TELEMETRIA  ·  SIN CUENTAS  ·  SIN CONEXION EXTERNA")
        footer.setObjectName("statusLabel")
        layout.addWidget(footer)

    def _micro(self, text):
        label = QLabel(text)
        label.setObjectName("microLabel")
        return label

    def _stat(self, parent_layout, caption, initial):
        box = QVBoxLayout()
        caption_label = QLabel(caption)
        caption_label.setObjectName("microLabel")
        value = QLabel(initial)
        value.setObjectName("statNumber")
        box.addWidget(caption_label)
        box.addWidget(value)
        container = QWidget()
        container.setLayout(box)
        parent_layout.addWidget(container)
        return value

    def refresh_stats(self):
        report = getattr(self.mw, "last_report", None)
        if report is not None:
            found = len(report.found_entries)
            count_to(self.stat_traces, found, formatter=str)
            self.stat_size.setText(fmt_bytes(report.total_bytes))
            self.stat_last.setText(report.scanned_at)
        freed = getattr(self.mw, "session_freed_bytes", 0)
        count_to(self.stat_freed, freed, formatter=fmt_bytes)

    def _go_scan(self):
        self.mw.navigate(1)
        self.mw.scan_view.start_scan()
