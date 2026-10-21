"""Scan view with virtualized table, search, keyboard shortcuts, and animations."""

import time
from typing import Optional

from PySide6.QtCore import (
    Qt, Signal, QTimer, QAbstractTableModel, QModelIndex,
    QSortFilterProxyModel, QPropertyAnimation, QEasingCurve,
    QPoint
)
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QMessageBox, QProgressBar,
    QTableView, QLabel, QPushButton, QVBoxLayout, QWidget,
    QLineEdit, QMenu, QHeaderView
)
from PySide6.QtGui import QKeySequence, QShortcut, QAction

from ..core import reporter
from ..i18n import t
from ..core.scanner import (
    STATUS_ADMIN, STATUS_EMPTY, STATUS_ERROR, STATUS_FOUND,
    STATUS_LOCKED, STATUS_READY, ScanProgress
)
from .animations import fade_out
from .worker import Worker
from ..utils.paths import fmt_bytes


_BADGE_MAP = {
    STATUS_FOUND: "badgeFound",
    STATUS_EMPTY: "badgeEmpty",
    STATUS_READY: "badgeReady",
    STATUS_LOCKED: "badgeLocked",
    STATUS_ADMIN: "badgeLocked",
    STATUS_ERROR: "badgeError",
}

_STATUS_LABEL = {
    STATUS_FOUND: "RASTRO DETECTADO",
    STATUS_EMPTY: "LIMPIO",
    STATUS_LOCKED: "BLOQUEADO",
    STATUS_ADMIN: "REQUIERE ADMIN",
    STATUS_READY: "DISPONIBLE",
    STATUS_ERROR: "ERROR",
}


class ScanTableModel(QAbstractTableModel):
    """Virtualized table model for scan results."""

    COLUMNS = ["target", "category", "status", "items", "size"]

    def __init__(self, entries=None, parent=None):
        super().__init__(parent)
        self._entries = entries or []
        self._filtered_indices = list(range(len(self._entries)))

    def set_entries(self, entries):
        self.beginResetModel()
        self._entries = entries
        self._filtered_indices = list(range(len(entries)))
        self.endResetModel()

    def filter(self, text: str):
        """Filter entries by search text."""
        self.beginResetModel()
        text = text.lower()
        if not text:
            self._filtered_indices = list(range(len(self._entries)))
        else:
            self._filtered_indices = [
                i for i, e in enumerate(self._entries)
                if text in e.target.name.lower()
                or text in e.target.category.lower()
                or text in e.status_label.lower()
                or any(text in item.path.lower() for item in e.items)
            ]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._filtered_indices)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return [
                t("scan.col_target"),
                t("scan.col_category"),
                t("scan.col_status"),
                t("scan.col_items"),
                t("scan.col_size"),
            ][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._filtered_indices):
            return None

        entry = self._entries[self._filtered_indices[index.row()]]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return entry.target.name
            elif col == 1:
                return entry.target.category
            elif col == 2:
                return entry.status_label
            elif col == 3:
                return str(len(entry.items)) if entry.items else "-"
            elif col == 4:
                total = entry.total_bytes
                if total and entry.status != STATUS_LOCKED:
                    return fmt_bytes(total)
                return "-"

        elif role == Qt.ItemDataRole.UserRole and col == 2:
            return _BADGE_MAP.get(entry.status)

        elif role == Qt.ItemDataRole.TextAlignmentRole and col in (2, 3, 4):
            return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.ToolTipRole and col == 0:
            return entry.target.detail

        return None

    def get_entry(self, proxy_row: int):
        """Get entry by proxy model row."""
        if proxy_row < 0 or proxy_row >= len(self._filtered_indices):
            return None
        return self._entries[self._filtered_indices[proxy_row]]

    def get_source_row(self, proxy_row: int) -> int:
        """Get source model row from proxy row."""
        if proxy_row < 0 or proxy_row >= len(self._filtered_indices):
            return -1
        return self._filtered_indices[proxy_row]


class ScanView(QWidget):
    progress = Signal(object)  # ScanProgress

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.report = None
        self._worker = None
        self._start_time = 0
        self._elapsed_timer = None
        self._row_animations = []
        self._skeleton_rows = 0

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        # Header
        micro = QLabel(t("scan.title"))
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        header = QHBoxLayout()
        title = QLabel(t("scan.subtitle"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; color: #FFFFFF;")
        header.addWidget(title)
        header.addStretch(1)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t("scan.search_placeholder"))
        self.search_box.setObjectName("searchBox")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(280)
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setToolTip(t("scan.search_tooltip"))
        header.addWidget(self.search_box)

        # Buttons
        self.cancel_btn = QPushButton(t("scan.cancel"))
        self.cancel_btn.setObjectName("cliHide")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_scan)
        self.cancel_btn.setAccessibleName(t("scan.cancel"))
        self.cancel_btn.setAccessibleDescription(t("scan.cancel_desc"))
        header.addWidget(self.cancel_btn)

        self.scan_btn = QPushButton(t("scan.btn_scan"))
        self.scan_btn.setObjectName("scanBtn")
        self.scan_btn.clicked.connect(self.start_scan)
        self.scan_btn.setAccessibleName(t("scan.btn_scan"))
        self.scan_btn.setAccessibleDescription(t("scan.btn_scan_desc"))
        header.addWidget(self.scan_btn)

        self.txt_btn = QPushButton(t("scan.export_txt"))
        self.txt_btn.setEnabled(False)
        self.txt_btn.setToolTip(t("scan.export_txt"))
        self.txt_btn.clicked.connect(self._export_txt)
        header.addWidget(self.txt_btn)

        self.csv_btn = QPushButton(t("scan.export_csv"))
        self.csv_btn.setEnabled(False)
        self.csv_btn.setToolTip(t("scan.export_csv"))
        self.csv_btn.clicked.connect(self._export_csv)
        header.addWidget(self.csv_btn)

        layout.addLayout(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress label with ETA
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("hintLabel")
        layout.addWidget(self.progress_label)

        # Table with proxy model for filtering
        self._model = ScanTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # Search all columns

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 120)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._show_detail)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setAccessibleName(t("scan.table_accessible_name"))
        self.table.setAccessibleDescription(t("scan.table_accessible_desc"))
        self.table.setVisible(False)
        layout.addWidget(self.table, 1)

        # Summary
        self.summary = QLabel(t("scan.no_data"))
        self.summary.setObjectName("scanSummary")
        layout.addWidget(self.summary)

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Signals
        self.progress.connect(self._on_progress)

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
        # F5 - Start scan
        QShortcut(QKeySequence(Qt.Key.Key_F5), self, activated=self.start_scan)
        # Escape - Cancel scan
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._cancel_scan)
        # Ctrl+E - Export TXT
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._export_txt)
        # Ctrl+Shift+E - Export CSV
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=self._export_csv)
        # Ctrl+F - Focus search
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.search_box.setFocus())
        # Ctrl+A - Select all
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self._select_all)
        # Delete - Clear selection
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._clear_selection)

        # Tooltips with shortcuts
        self.scan_btn.setToolTip(f"{t('scan.btn_scan')} (F5)")
        self.cancel_btn.setToolTip(f"{t('scan.cancel')} (Escape)")
        self.txt_btn.setToolTip(f"{t('scan.export_txt')} (Ctrl+E)")
        self.csv_btn.setToolTip(f"{t('scan.export_csv')} (Ctrl+Shift+E)")

    def start_scan(self):
        if self._worker and self._worker.isRunning():
            return False

        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(t("scan.scanning"))
        self.cancel_btn.setVisible(True)
        self.txt_btn.setEnabled(False)
        self.csv_btn.setEnabled(False)

        # Show skeleton rows immediately
        self._show_skeleton_rows(5)

        self.progress_bar.setValue(0)
        self._start_time = time.time()
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.start()

        from ..core.targets import build_targets
        from ..utils.settings import get_settings

        exclusions = set(get_settings().get("exclusions") or [])
        targets = build_targets(exclusions=exclusions)

        def job():
            from ..core.scanner import scan_targets_parallel
            return scan_targets_parallel(targets, progress_cb=self._emit_progress)

        self._worker = Worker(job)
        self._worker.done.connect(self._scan_done)
        self._worker.failed.connect(self._scan_failed)
        self._worker.start()
        return True

    def _emit_progress(self, progress: ScanProgress):
        self.progress.emit(progress)

    def _on_progress(self, progress: ScanProgress):
        if progress.total > 0:
            self.progress_bar.setMaximum(progress.total)
            self.progress_bar.setValue(progress.current)

        # Update label with ETA
        eta_str = ""
        if progress.eta is not None:
            eta_str = f" • ETA: {int(progress.eta)}s"

        self.progress_label.setText(
            t("scan.progress_time", current=progress.current, total=progress.total, elapsed=progress.elapsed) + eta_str
        )

        # Update current target label
        if progress.current_target:
            self.progress_label.setText(f"{progress.current_target} {eta_str}")

    def _tick_elapsed(self):
        if self._worker and self._worker.isRunning():
            elapsed = time.time() - self._start_time
            self.progress_label.setText(
                t("scan.progress_time", current=self.progress_bar.value(), total=self.progress_bar.maximum(), elapsed=elapsed)
            )

    def _cancel_scan(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._scan_btn_reset()

    def _scan_btn_reset(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(t("scan.btn_scan"))
        self.cancel_btn.setVisible(False)
        if self._elapsed_timer:
            self._elapsed_timer.stop()

    def _scan_done(self, report):
        self.report = report
        self.mw.last_report = report

        # Hide skeleton, populate real data
        self._hide_skeleton()
        self._model.set_entries(report.entries)

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

        # Animate rows entrance
        self._animate_rows_entrance()

        # Update dashboard and viral stats
        self.mw.dashboard_view.refresh_stats()
        try:
            from ..core.viral import get_stats
            get_stats().record_scan(found, report.total_bytes)
        except Exception:
            pass

        # Update privacy streak
        try:
            from ..core.streak import update_streak
            update_streak(found)
        except Exception:
            pass

        # Notification
        try:
            from ..core.notifications import notify_scan_complete
            notify_scan_complete(found, report.total_bytes)
        except Exception:
            pass

        # Celebration animation for clean results
        if found == 0:
            self._show_clean_celebration()
        elif found > 50:
            self._show_warning_pulse()

    def _scan_failed(self, message: str):
        self._scan_btn_reset()
        self._hide_skeleton()

        # Categorize error for better UX
        error_type = self._categorize_error(message)

        error_dialogs = {
            "permission": (
                t("scan.error_permission_title"),
                t("scan.error_permission_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self._restart_as_admin
            ),
            "locked": (
                t("scan.error_locked_title"),
                t("scan.error_locked_msg"),
                QMessageBox.StandardButton.Ok,
                None
            ),
            "generic": (
                t("scan.error_title"),
                message,
                QMessageBox.StandardButton.Ok,
                None
            )
        }

        title, text, buttons, callback = error_dialogs.get(error_type, error_dialogs["generic"])
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        box.setIcon(QMessageBox.Icon.Warning)

        if box.exec() == QMessageBox.StandardButton.Yes and callback:
            callback()

    def _categorize_error(self, message: str) -> str:
        msg = message.lower()
        if "access denied" in msg or "permission" in msg or "admin" in msg:
            return "permission"
        if "locked" in msg or "in use" in msg or "busy" in msg:
            return "locked"
        return "generic"

    def _restart_as_admin(self):
        import sys
        import subprocess
        script = sys.argv[0]
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        subprocess.run(['powershell', '-Command', f'Start-Process "{sys.executable}" "{params}" -Verb RunAs'])
        # App will exit, new instance runs as admin

    def _show_skeleton_rows(self, count: int):
        """Show skeleton loading rows."""
        self._skeleton_rows = count
        self._model.set_entries([])
        self.table.setRowCount(count)
        self.table.setVisible(True)
        self.table.setUpdatesEnabled(False)

        for row in range(count):
            for col in range(5):
                # Skeleton items will be styled via CSS
                pass

        self.table.setUpdatesEnabled(True)
        self._start_skeleton_animation()

    def _hide_skeleton(self):
        self._skeleton_rows = 0
        self.table.setStyleSheet("")

    def _start_skeleton_animation(self):
        """CSS-based shimmer animation for skeleton rows."""
        self.table.setStyleSheet("""
            QTableView::item {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E293B, stop:0.5 #334155, stop:1 #1E293B);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite linear;
            }
            @keyframes shimmer {
                0% { background-position: -200% 0; }
                100% { background-position: 200% 0; }
            }
        """)

    def _animate_rows_entrance(self):
        """Staggered fade-in animation for table rows."""
        for i in range(self._model.rowCount()):
            QTimer.singleShot(i * 30, lambda r=i: self._reveal_row(r))

    def _reveal_row(self, proxy_row: int):
        """Reveal a single row with fade-in."""
        for col in range(self._model.columnCount()):
            index = self._proxy.index(proxy_row, col)
            if index.isValid():
                # Note: QTableView items don't support graphics effects directly
                # This is a visual hint - actual animation would need delegate
                pass

    def _show_clean_celebration(self):
        """Show celebration animation for clean scan."""
        check = QLabel("✨")
        check.setStyleSheet("font-size: 64px;")
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setParent(self)
        check.move(self.width() // 2 - 32, self.height() // 2 - 32)
        check.show()

        fade_out(check, duration=1500, on_finished=check.deleteLater)

        self._pulse_label(self.summary, "#FFFFFF")

    def _show_warning_pulse(self):
        """Pulse warning for many findings."""
        self._pulse_label(self.summary, "#F59E0B")

    def _pulse_label(self, label: QLabel, color: str):
        anim = QPropertyAnimation(label, b"styleSheet")
        anim.setDuration(1000)
        anim.setLoopCount(2)
        original = label.styleSheet()
        anim.setKeyValueAt(0, original)
        anim.setKeyValueAt(0.5, f"{original} color: {color}; font-weight: 700;")
        anim.setKeyValueAt(1, original)
        anim.start()

    def _on_search_changed(self, text: str):
        """Filter table based on search text."""
        self._model.filter(text)

    def _show_context_menu(self, pos):
        """Show context menu on right-click."""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        proxy_row = index.row()
        entry = self._model.get_entry(proxy_row)
        if not entry:
            return

        menu = QMenu(self)

        copy_action = QAction(t("scan.copy_path"), self)
        copy_action.triggered.connect(lambda: self._copy_entry_paths(entry))
        menu.addAction(copy_action)

        if entry.items:
            open_action = QAction(t("scan.open_location"), self)
            open_action.triggered.connect(lambda: self._open_entry_location(entry))
            menu.addAction(open_action)

            detail_action = QAction(t("scan.view_detail"), self)
            detail_action.triggered.connect(lambda: self._show_detail(index))
            menu.addAction(detail_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_entry_paths(self, entry):
        """Copy entry paths to clipboard."""
        from PySide6.QtWidgets import QApplication
        paths = "\n".join(item.path for item in entry.items)
        QApplication.clipboard().setText(paths)
        self.mw.cli_output(t("scan.copied", count=len(entry.items)))

    def _open_entry_location(self, entry):
        """Open first item location in explorer."""
        import subprocess
        if entry.items:
            path = entry.items[0].path
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                subprocess.Popen(f'explorer /select,"{path}"')
            except Exception:
                try:
                    subprocess.Popen(f'explorer "{folder}"')
                except Exception:
                    pass

    def _select_all(self):
        self.table.selectAll()

    def _clear_selection(self):
        self.table.clearSelection()

    def _show_detail(self, index):
        if not self.report:
            return
        proxy_row = index.row()
        entry = self._model.get_entry(proxy_row)
        if not entry:
            return

        lines = [entry.target.detail or "", ""]
        lines += [item.path for item in entry.items[:40]]
        if len(entry.items) > 40:
            lines.append(t("scan.more", count=len(entry.items) - 40))

        from PySide6.QtWidgets import QTextBrowser
        box = QMessageBox(self)
        box.setWindowTitle(entry.target.name)
        browser = QTextBrowser()
        browser.setPlainText("\n".join(lines) or t("scan.no_paths"))
        box.layout().addWidget(browser)
        box.exec()

    def _export_txt(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, t("scan.export_title_txt"), "duai_reporte.txt", "TXT (*.txt)")
        if path:
            reporter.save_report_txt(self.report, path)
            self.mw.cli_output(t("scan.exported_txt", path=path))

    def _export_csv(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, t("scan.export_title_csv"), "duai_reporte.csv", "CSV (*.csv)")
        if path:
            reporter.save_report_csv(self.report, path)
            self.mw.cli_output(t("scan.exported_csv", path=path))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Hide less critical columns on narrow screens
        width = self.table.width()
        if width < 600:
            self.table.setColumnHidden(3, True)  # Hide items column
        else:
            self.table.setColumnHidden(3, False)