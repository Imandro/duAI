from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import reporter
from ..core.scanner import (
    STATUS_ADMIN,
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_FOUND,
    STATUS_LOCKED,
    STATUS_READY,
)
from .worker import Worker


class ScanView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.report = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        micro = QLabel("DETECTOR DE RASTROS")
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        header = QHBoxLayout()
        title = QLabel("Escaneo")
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        header.addWidget(title)
        header.addStretch(1)
        self.scan_btn = QPushButton("ESCANEAR")
        self.scan_btn.clicked.connect(self.start_scan)
        self.txt_btn = QPushButton("EXPORTAR TXT")
        self.txt_btn.clicked.connect(self._export_txt)
        self.csv_btn = QPushButton("EXPORTAR CSV")
        self.csv_btn.clicked.connect(self._export_csv)
        for btn in (self.txt_btn, self.csv_btn):
            btn.setEnabled(False)
            header.addWidget(btn)
        header.addWidget(self.scan_btn)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["OBJETIVO", "CATEGORIA", "ESTADO", "ELEMENTOS", "TAMAÑO"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 90)
        self.table.doubleClicked.connect(self._show_detail)
        layout.addWidget(self.table, 1)

        self.summary = QLabel("SIN DATOS. EJECUTA UN ESCANEO.")
        self.summary.setObjectName("statusLabel")
        layout.addWidget(self.summary)

    def start_scan(self):
        if self._worker and self._worker.isRunning():
            return False
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("ESCANEANDO...")
        from ..core.targets import build_targets
        from ..utils.settings import get_settings

        exclusions = set(get_settings().get("exclusions") or [])
        targets = build_targets(exclusions=exclusions)

        def job():
            from ..core.scanner import scan_targets

            return scan_targets(targets)

        self._worker = Worker(job)
        self._worker.done.connect(self._scan_done)
        self._worker.failed.connect(self._scan_failed)
        self._worker.start()
        return True

    def _scan_done(self, report):
        self.report = report
        self.mw.last_report = report
        self._fill_table(report)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("ESCANEAR")
        self.txt_btn.setEnabled(True)
        self.csv_btn.setEnabled(True)
        found = len(report.found_entries)
        self.summary.setText(
            f"{found} OBJETIVOS CON RASTROS · {report.total_bytes} BYTES · {report.scanned_at}"
        )
        self.mw.dashboard_view.refresh_stats()

    def _scan_failed(self, message):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("ESCANEAR")
        QMessageBox.warning(self, "duAI", "Error durante el escaneo: " + message)

    def _fill_table(self, report):
        from PySide6.QtGui import QColor

        from .theme import color

        entries = sorted(report.entries, key=lambda e: e.status != STATUS_FOUND)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.target.name,
                entry.target.category,
                entry.status_label,
                str(len(entry.items)) if entry.items else "-",
                _size_cell(entry),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if entry.status in (STATUS_EMPTY, STATUS_READY):
                    item.setForeground(QColor(color("SOFT")))
                elif entry.status in (STATUS_LOCKED, STATUS_ADMIN, STATUS_ERROR):
                    item.setForeground(QColor(color("BODY")))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 300)

    def _show_detail(self, index):
        if not self.report:
            return
        row = index.row()
        name = self.table.item(row, 0).text()
        for entry in self.report.entries:
            if entry.target.name == name:
                lines = [entry.target.detail or "", ""]
                lines += [item.path for item in entry.items[:40]]
                if len(entry.items) > 40:
                    lines.append(f"... y {len(entry.items) - 40} mas")
                box = QMessageBox(self)
                box.setWindowTitle(entry.target.name)
                browser = QTextBrowser()
                browser.setPlainText("\n".join(lines) or "Sin rutas")
                box.layout().addWidget(browser)
                box.exec()
                return

    def _export_txt(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar TXT", "duai_reporte.txt", "TXT (*.txt)")
        if path:
            reporter.save_report_txt(self.report, path)

    def _export_csv(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "duai_reporte.csv", "CSV (*.csv)")
        if path:
            reporter.save_report_csv(self.report, path)


def _size_cell(entry):
    from ..utils.paths import fmt_bytes

    total = entry.total_bytes
    if total and entry.status != STATUS_LOCKED:
        return fmt_bytes(total)
    return "-"
