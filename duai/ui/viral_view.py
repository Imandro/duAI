from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from ..core.viral import (
    get_stats,
    generate_share_report,
    copy_to_clipboard,
    open_share_url,
)
from ..i18n import t
from ..utils.settings import get_settings
from .animations import count_to


class ViralView(QWidget):
    """Pantalla de logros (gamificacion) y reporte para compartir en redes."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.stats = get_stats()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("viral.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)

        title = QLabel(t("viral.achievements"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; letter-spacing: 2px; color: #FFFFFF;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.ach_layout = QVBoxLayout(content)
        self.ach_layout.setContentsMargins(0, 0, 16, 0)
        self.ach_layout.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Estadisticas
        stats_box = QFrame()
        stats_box.setObjectName("statCard")
        stats_layout = QVBoxLayout(stats_box)
        stats_layout.setContentsMargins(16, 16, 16, 16)
        stats_layout.setSpacing(8)

        stat_title = QLabel(t("viral.stats"))
        stat_title.setObjectName("microLabel")
        stats_layout.addWidget(stat_title)

        self.stat_scans = self._stat_row(stats_layout, t("viral.scans"), str(self.stats.get("scans", 0)))
        self.stat_cleans = self._stat_row(stats_layout, t("viral.cleans"), str(self.stats.get("cleans", 0)))
        self.stat_panics = self._stat_row(stats_layout, t("viral.panics"), str(self.stats.get("panics", 0)))
        self.stat_freed = self._stat_row(stats_layout, t("viral.freed"), "0 B")
        self.stat_streak = self._stat_row(stats_layout, t("viral.streak"), str(self.stats.get("streak_days", 0)))
        outer.addWidget(stats_box)

        # Acciones de compartir
        share_row = QHBoxLayout()
        self.share_btn = QPushButton(t("viral.share"))
        self.share_btn.setObjectName("shareBtn")
        self.share_btn.clicked.connect(self._share)
        copy_btn = QPushButton(t("viral.copy_report"))
        copy_btn.clicked.connect(self._copy_report)
        share_row.addWidget(self.share_btn)
        share_row.addWidget(copy_btn)
        share_row.addStretch(1)
        outer.addLayout(share_row)

        hint = QLabel(t("viral.report_title"))
        hint.setObjectName("shareHint")
        outer.addWidget(hint)

        self.refresh()

    def _stat_row(self, parent, caption, initial):
        row = QHBoxLayout()
        lbl = QLabel(caption)
        lbl.setObjectName("microLabel")
        value = QLabel(initial)
        value.setObjectName("statNumber")
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(value)
        parent.addLayout(row)
        return value

    def refresh(self):
        # Limpiar logros previos
        while self.ach_layout.count():
            child = self.ach_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        achievements = self.stats.unlocked_achievements()
        if not achievements:
            empty = QLabel(t("viral.no_achievements"))
            empty.setObjectName("statusLabel")
            self.ach_layout.addWidget(empty)
        else:
            for ach in achievements:
                frame = QFrame()
                frame.setObjectName("achievement")
                frame.setProperty("achievement", "unlocked" if ach["unlocked"] else "locked")
        if ach["unlocked"]:
            frame.setStyleSheet("border: 1px solid #FFFFFF;")
        else:
            frame.setStyleSheet("opacity: 0.4;")
        frame.setStyleSheet("")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(4)
        name = QLabel(ach["name"])
        name.setObjectName("name")
        box.addWidget(name)
        desc = QLabel(ach["desc"])
        desc.setObjectName("desc")
        desc.setWordWrap(True)
        box.addWidget(desc)
        self.ach_layout.addWidget(frame)

        # Actualizar stats animados
        count_to(self.stat_scans, self.stats.get("scans", 0), formatter=str)
        count_to(self.stat_cleans, self.stats.get("cleans", 0), formatter=str)
        count_to(self.stat_panics, self.stats.get("panics", 0), formatter=str)
        from ..utils.paths import fmt_bytes
        count_to(self.stat_freed, self.stats.get("total_freed_bytes", 0), formatter=fmt_bytes)
        count_to(self.stat_streak, self.stats.get("streak_days", 0), formatter=str)

    def _share(self):
        platform = get_settings().get("share_platform") or "twitter"
        report = generate_share_report()
        url = open_share_url(platform, report)
        QDesktopServices.openUrl(QUrl(url))

    def _copy_report(self):
        report = generate_share_report()
        if copy_to_clipboard(report):
            self.mw.cli_output("Reporte copiado al portapapeles.")
        else:
            self.mw.cli_output("No se pudo copiar al portapapeles.")
