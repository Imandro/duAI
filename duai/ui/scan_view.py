import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import reporter
from ..i18n import t
from ..core.scanner import (
    STATUS_ADMIN,
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_FOUND,
    STATUS_LOCKED,
    STATUS_READY,
)
from .worker import Worker

_BADGE_MAP = {
    STATUS_FOUND: "badgeFound",
    STATUS_EMPTY: "badgeEmpty",
    STATUS_READY: "badgeReady",
    STATUS_LOCKED: "badgeLocked",
    STATUS_ADMIN: "badgeLocked",
    STATUS_ERROR: "badgeError",
}


class ScanView(QWidget):
    progress = Signal(int, int, str)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.report = None
        self._worker = None
        self._start_time = 0
        self._elapsed_timer = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        micro = QLabel(t("scan.title"))
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        header = QHBoxLayout()
        title = QLabel(t("scan.subtitle"))
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        header.addWidget(title)
        header.addStretch(1)
        self.cancel_btn = QPushButton(t("scan.cancel"))
        self.cancel_btn.setObjectName("cliHide")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_scan)
        header.addWidget(self.cancel_btn)
        self.scan_btn = QPushButton(t("scan.btn_scan"))
        self.scan_btn.clicked.connect(self.start_scan)
        self.txt_btn = QPushButton(t("scan.export_txt"))
        self.txt_btn.clicked.connect(self._export_txt)
        self.csv_btn = QPushButton(t("scan.export_csv"))
        self.csv_btn.clicked.connect(self._export_csv)
        for btn in (self.txt_btn, self.csv_btn):
            btn.setEnabled(False)
            header.addWidget(btn)
        header.addWidget(self.scan_btn)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("hintLabel")
        layout.addWidget(self.progress_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [t("scan.col_target"), t("scan.col_category"), t("scan.col_status"), t("scan.col_items"), t("scan.col_size")]
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
        self.table.setVisible(False)
        layout.addWidget(self.table, 1)

        self.summary = QLabel(t("scan.no_data"))
        self.summary.setObjectName("scanSummary")
        layout.addWidget(self.summary)

        self.progress.connect(self._on_progress)
        self._target_count = 0

    def start_scan(self):
        if self._worker and self._worker.isRunning():
            return False
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(t("scan.scanning"))
        self.cancel_btn.setVisible(True)
        self.txt_btn.setEnabled(False)
        self.csv_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.table.setVisible(False)
        self.progress_bar.setValue(0)
        self._start_time = time.time()
        self._elapsed_timer_obj = __import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer(self)
        self._elapsed_timer_obj.setInterval(200)
        self._elapsed_timer_obj.timeout.connect(self._tick_elapsed)
        self._elapsed_timer_obj.start()

        from ..core.targets import build_targets
        from ..utils.settings import get_settings

        exclusions = set(get_settings().get("exclusions") or [])
        targets = build_targets(exclusions=exclusions)
        self._target_count = len(targets)
        self.progress_label.setText(t("scan.progress", current=0, total=self._target_count))

        def job():
            from ..core.scanner import scan_targets_parallel

            return scan_targets_parallel(targets, progress_cb=self._emit_progress)

        self._worker = Worker(job)
        self._worker.done.connect(self._scan_done)
        self._worker.failed.connect(self._scan_failed)
        self._worker.start()
        return True

    def _emit_progress(self, current, total, name):
        self.progress.emit(current, total, name)

    def _on_progress(self, current, total, name):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        elapsed = time.time() - self._start_time
        self.progress_label.setText(
            t("scan.progress_time", current=current, total=total, elapsed=elapsed)
        )

    def _tick_elapsed(self):
        if self._worker and self._worker.isRunning():
            elapsed = time.time() - self._start_time
            self.progress_label.setText(
                t("scan.progress_time", current=self.progress_bar.value(), total=self._target_count, elapsed=elapsed)
            )

    def _cancel_scan(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._scan_btn_reset()

    def _scan_btn_reset(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(t("scan.btn_scan"))
        self.cancel_btn.setVisible(False)
        if hasattr(self, "_elapsed_timer_obj") and self._elapsed_timer_obj:
            self._elapsed_timer_obj.stop()

    def _scan_done(self, report):
        self.report = report
        self.mw.last_report = report
        self._fill_table(report)
        self._scan_btn_reset()
        self.txt_btn.setEnabled(True)
        self.csv_btn.setEnabled(True)
        self.table.setVisible(True)
        elapsed = time.time() - self._start_time
        found = len(report.found_entries)
        self.summary.setText(
            t("scan.done", found=found, bytes=report.total_bytes, elapsed=elapsed, time=report.scanned_at)
        )
        self.progress_label.setText("")
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.mw.dashboard_view.refresh_stats()

    def _scan_failed(self, message):
        self._scan_btn_reset()
        QMessageBox.warning(self, "duAI", t("scan.error") + message)

    def _fill_table(self, report):
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
                    badge = _BADGE_MAP.get(entry.status)
                    if badge:
                        item.setData(Qt.ItemDataRole.UserRole, badge)
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
                    lines.append(t("scan.more", count=len(entry.items) - 40))
                box = QMessageBox(self)
                box.setWindowTitle(entry.target.name)
                browser = QTextBrowser()
                browser.setPlainText("\n".join(lines) or t("scan.no_paths"))
                box.layout().addWidget(browser)
                box.exec()
                return

    def _export_txt(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, t("scan.export_title_txt"), "duai_reporte.txt", "TXT (*.txt)")
        if path:
            reporter.save_report_txt(self.report, path)

    def _export_csv(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, t("scan.export_title_csv"), "duai_reporte.csv", "CSV (*.csv)")
        if path:
            reporter.save_report_csv(self.report, path)


def _size_cell(entry):
    from ..utils.paths import fmt_bytes

    total = entry.total_bytes
    if total and entry.status != STATUS_LOCKED:
        return fmt_bytes(total)
    return "-"
