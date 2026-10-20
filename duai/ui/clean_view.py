"""Clean view with collapsible tree, tri-state checkboxes, keyboard shortcuts, and search."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
    QButtonGroup, QFrame, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QGraphicsDropShadowEffect, QProgressBar, QMenu
)
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QAction

from ..core.cleaner import CleanOptions, run_clean, CleanErrorType
from ..i18n import t
from .worker import Worker


class CleanView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        self._items_data = {}  # target_id -> entry data
        self._tree_items = {}  # target_id -> QTreeWidgetItem
        self._category_items = {}  # category -> QTreeWidgetItem (parent)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("clean.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)

        # Header with search
        header = QHBoxLayout()
        title = QLabel(t("clean.subtitle"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; color: #FFFFFF;")
        header.addWidget(title)
        header.addStretch(1)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t("clean.search_placeholder"))
        self.search_box.setObjectName("searchBox")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(280)
        self.search_box.textChanged.connect(self._filter_tree)
        self.search_box.setToolTip(t("clean.search_tooltip"))
        header.addWidget(self.search_box)

        self.run_btn = QPushButton(t("clean.btn_exec"))
        self.run_btn.setObjectName("cleanBtn")
        self.run_btn.clicked.connect(self.run_clean)
        self.run_btn.setAccessibleName(t("clean.btn_exec"))
        self.run_btn.setAccessibleDescription(t("clean.btn_exec_desc"))
        header.addWidget(self.run_btn)
        outer.addLayout(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        outer.addWidget(self.progress_bar)

        # Tree widget for collapsible categories
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("clean.col_target"), t("clean.col_size"), t("clean.col_risk")])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 100)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setAccessibleName(t("clean.tree_accessible_name"))
        self.tree.setAccessibleDescription(t("clean.tree_accessible_desc"))
        outer.addWidget(self.tree, 1)

        # Options row
        options_row = QHBoxLayout()
        self.preview_check = QCheckBox(t("clean.preview"))
        self.preview_check.setChecked(True)
        self.preview_check.setToolTip(f"{t('clean.preview')} (Ctrl+P)")
        self.preview_check.setAccessibleName(t("clean.preview"))
        self.preview_check.setAccessibleDescription(t("clean.preview_desc"))

        self.recycle_radio = QRadioButton(t("clean.mode_recycle"))
        self.recycle_radio.setChecked(True)
        self.recycle_radio.setToolTip(t("clean.mode_recycle_tooltip"))
        self.quarantine_radio = QRadioButton(t("clean.mode_quarantine"))
        self.quarantine_radio.setToolTip(t("clean.mode_quarantine_tooltip"))
        self.permanent_radio = QRadioButton(t("clean.mode_permanent"))
        self.permanent_radio.setToolTip(t("clean.mode_permanent_tooltip"))

        mode_group = QButtonGroup(self)
        for radio in (self.recycle_radio, self.quarantine_radio, self.permanent_radio):
            mode_group.addButton(radio)
            radio.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.select_all_btn = QPushButton(t("clean.select_all"))
        self.select_all_btn.setToolTip(f"{t('clean.select_all')} (Ctrl+A)")
        self.select_all_btn.clicked.connect(self._select_all)
        self.clear_all_btn = QPushButton(t("clean.deselect_all"))
        self.clear_all_btn.setToolTip(f"{t('clean.deselect_all')} (Ctrl+Shift+A)")
        self.clear_all_btn.clicked.connect(self._deselect_all)

        options_row.addWidget(self.preview_check)
        options_row.addWidget(self.recycle_radio)
        options_row.addWidget(self.quarantine_radio)
        options_row.addWidget(self.permanent_radio)
        options_row.addStretch(1)
        options_row.addWidget(self.select_all_btn)
        options_row.addWidget(self.clear_all_btn)
        outer.addLayout(options_row)

        # Log view
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(180)
        self.log_view.setPlaceholderText(t("clean.placeholder"))
        outer.addWidget(self.log_view)

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Build tree
        self._build_tree()

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self._select_all)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self._deselect_all)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.run_clean)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.run_clean)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self._toggle_selected)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=lambda: self.preview_check.toggle())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.search_box.setFocus())
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._deselect_all)

        # Tooltips with shortcuts
        self.run_btn.setToolTip(f"{t('clean.btn_exec')} (Ctrl+Return / Enter)")
        self.select_all_btn.setToolTip(f"{t('clean.select_all')} (Ctrl+A)")
        self.clear_all_btn.setToolTip(f"{t('clean.deselect_all')} (Ctrl+Shift+A)")
        self.preview_check.setToolTip(f"{t('clean.preview')} (Ctrl+P)")

    def _build_tree(self):
        """Build collapsible tree by category."""
        from ..core.targets import list_all_entries
        from ..utils.settings import get_settings

        exclusions = set(get_settings().get("exclusions") or [])
        entries = [e for e in list_all_entries() if e["id"] not in exclusions]

        # Group by category
        categories = {}
        for entry in entries:
            cat = entry["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(entry)

        # Category icons
        category_icons = {
            "cache": "🗂️", "logs": "📋", "temp": "🗑️",
            "browser": "🌐", "thumbnails": "🖼️", "trash": "🗑️",
            "registry": "📝", "dns": "🌐", "clipboard": "📋",
            "timeline": "📅", "location": "📍", "system": "⚙️",
        }

        # Create tree structure
        for category_name, items in sorted(categories.items()):
            icon = category_icons.get(category_name.lower(), "📁")
            parent = QTreeWidgetItem(self.tree, [f"{icon}  {category_name.upper()}", "", ""])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            parent.setData(0, Qt.ItemDataRole.UserRole, {"category": category_name, "is_category": True})
            parent.setExpanded(True)
            self._category_items[category_name] = parent

            for entry in sorted(items, key=lambda e: e["name"]):
                self._add_entry_item(parent, entry)

        # Connect tristate handling
        self.tree.itemChanged.connect(self._on_item_changed)

    def _add_entry_item(self, parent, entry):
        """Add a single entry as tree item with size and risk badges."""
        item = QTreeWidgetItem(parent, [
            entry["name"],
            "",  # Size will be populated after scan
            self._risk_badge(entry)
        ])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setData(0, Qt.ItemDataRole.UserRole, {"entry": entry, "is_category": False})
        item.setToolTip(0, entry.get("description", ""))
        self._tree_items[entry["id"]] = item
        self._items_data[entry["id"]] = entry

    def _risk_badge(self, entry) -> str:
        """Generate risk badge based on entry type."""
        risk_map = {
            "browser_history": "🔴 Alto",
            "browser_storage": "🟠 Medio",
            "registry": "🟠 Medio",
            "cache": "🟢 Bajo",
            "logs": "🟢 Bajo",
            "temp": "🟢 Bajo",
            "dns": "🟢 Bajo",
            "clipboard": "🟡 Bajo",
            "timeline": "🟡 Medio",
            "location": "🟡 Medio",
        }
        return risk_map.get(entry.get("kind", ""), "⚪ Desconocido")

    def _on_item_changed(self, item, column):
        """Handle tristate checkbox changes."""
        if column != 0:
            return

        # Block signals to avoid recursion
        self.tree.blockSignals(True)

        if item.data(0, Qt.ItemDataRole.UserRole).get("is_category"):
            # Category item - propagate to children
            state = item.checkState(0)
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, state)
        else:
            # Leaf item - update parent tristate
            parent = item.parent()
            if parent:
                self._update_parent_check_state(parent)

        self.tree.blockSignals(False)

    def _update_parent_check_state(self, parent):
        """Update parent check state based on children."""
        checked = 0
        unchecked = 0
        for i in range(parent.childCount()):
            child = parent.child(i)
            state = child.checkState(0)
            if state == Qt.CheckState.Checked:
                checked += 1
            elif state == Qt.CheckState.Unchecked:
                unchecked += 1

        if checked == parent.childCount():
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked == parent.childCount():
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _filter_tree(self, text: str):
        """Filter tree items by search text."""
        text = text.lower()
        for target_id, item in self._tree_items.items():
            visible = True
            if text:
                entry_data = item.data(0, Qt.ItemDataRole.UserRole)
                entry = entry_data.get("entry")
                if entry:
                    visible = (text in entry["name"].lower() or
                              text in entry.get("description", "").lower() or
                              text in entry["category"].lower())
            item.setHidden(not visible)

        # Show/hide categories based on children visibility
        for cat, cat_item in self._category_items.items():
            any_visible = False
            for i in range(cat_item.childCount()):
                if not cat_item.child(i).isHidden():
                    any_visible = True
                    break
            cat_item.setHidden(not any_visible)

    def _select_all(self):
        """Select all visible items."""
        self.tree.blockSignals(True)
        for item in self._tree_items.values():
            if not item.isHidden():
                item.setCheckState(0, Qt.CheckState.Checked)
        for cat_item in self._category_items.values():
            if not cat_item.isHidden():
                cat_item.setCheckState(0, Qt.CheckState.Checked)
        self.tree.blockSignals(False)

    def _deselect_all(self):
        """Deselect all items."""
        self.tree.blockSignals(True)
        for item in self._tree_items.values():
            item.setCheckState(0, Qt.CheckState.Unchecked)
        for cat_item in self._category_items.values():
            cat_item.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)

    def _toggle_selected(self):
        """Toggle check state of selected items."""
        selected = self.tree.selectedItems()
        if not selected:
            return
        self.tree.blockSignals(True)
        for item in selected:
            if not item.isHidden():
                new_state = Qt.CheckState.Checked if item.checkState(0) == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked
                item.setCheckState(0, new_state)
        self.tree.blockSignals(False)

    def _show_context_menu(self, pos):
        """Show context menu on right-click."""
        item = self.tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)

        if item.data(0, Qt.ItemDataRole.UserRole).get("is_category"):
            expand_all = QAction(t("clean.expand_all"), self)
            expand_all.triggered.connect(lambda: self._expand_category(item, True))
            menu.addAction(expand_all)

            collapse_all = QAction(t("clean.collapse_all"), self)
            collapse_all.triggered.connect(lambda: self._expand_category(item, False))
            menu.addAction(collapse_all)
        else:
            copy_action = QAction(t("clean.copy_path"), self)
            copy_action.triggered.connect(lambda: self._copy_item_path(item))
            menu.addAction(copy_action)

            open_action = QAction(t("clean.open_location"), self)
            open_action.triggered.connect(lambda: self._open_item_location(item))
            menu.addAction(open_action)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _expand_category(self, item, expand: bool):
        item.setExpanded(expand)
        for i in range(item.childCount()):
            item.child(i).setExpanded(expand)

    def _copy_item_path(self, item):
        entry_data = item.data(0, Qt.ItemDataRole.UserRole)
        entry = entry_data.get("entry")
        if entry:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(entry.get("detail", ""))
            self.mw.cli_output(t("clean.copied"))

    def _open_item_location(self, item):
        entry_data = item.data(0, Qt.ItemDataRole.UserRole)
        entry = entry_data.get("entry")
        if entry and entry.get("paths"):
            import subprocess
            path = entry["paths"][0]
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                subprocess.Popen(f'explorer /select,"{path}"')
            except Exception:
                try:
                    subprocess.Popen(f'explorer "{folder}"')
                except Exception:
                    pass

    def selected_ids(self):
        """Get selected target IDs."""
        selected = set()
        for target_id, item in self._tree_items.items():
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.add(target_id)
        return selected

    def apply_cli(self, target_ids, mode, confirm):
        mode_radio = {
            "recycle": self.recycle_radio,
            "quarantine": self.quarantine_radio,
            "permanent": self.permanent_radio,
        }.get(mode, self.recycle_radio)
        mode_radio.setChecked(True)
        for target_id, item in self._tree_items.items():
            item.setCheckState(0, Qt.CheckState.Checked if target_id in target_ids else Qt.CheckState.Unchecked)
        self.preview_check.setChecked(not confirm)
        if not self.selected_ids():
            return False
        self.run_clean()
        return True

    def run_clean(self):
        if self._worker and self._worker.isRunning():
            return

        selected = self.selected_ids()
        if not selected:
            self._show_inline_error(t("clean.select_target"))
            self._shake_widget(self.run_btn)
            return

        if self.permanent_radio.isChecked():
            mode = "permanent"
        elif self.quarantine_radio.isChecked():
            mode = "quarantine"
        else:
            mode = "recycle"
        preview = self.preview_check.isChecked()

        # Multi-level confirmation
        if not self._confirm_action(mode, preview, len(selected)):
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText(t("clean.processing"))
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        def job():
            from ..core.scanner import scan_targets_parallel
            from ..core.targets import build_targets
            from ..utils.settings import get_settings

            exclusions = set(get_settings().get("exclusions") or [])
            targets = [t for t in build_targets(exclusions=exclusions) if t.id in selected]

            # Simulate progress
            import time
            before_report = scan_targets_parallel(targets)
            options = CleanOptions(
                selected=set(t.id for t in targets),
                mode=mode,
                preview=preview,
            )
            result = run_clean(before_report, options)
            after_report = scan_targets_parallel(targets)
            return result, before_report, after_report

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _confirm_action(self, mode: str, preview: bool, selected_count: int) -> bool:
        """Multi-level safety confirmation."""
        from ..utils.settings import get_settings

        settings = get_settings()

        # Level 1: Permanent deletion without preview - strongest warning
        if mode == "permanent" and not preview:
            skip_key = settings.get("confirm_permanent_skip", False)
            if not skip_key:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(t("clean.confirm_permanent_title"))
                msg_box.setText(t("clean.confirm_permanent_msg", count=selected_count))
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                cb = QCheckBox(t("clean.dont_ask_again"))
                msg_box.setCheckBox(cb)
                if msg_box.exec() == QMessageBox.StandardButton.Yes:
                    if cb.isChecked():
                        settings.set("confirm_permanent_skip", True)
                    return True
                return False

        # Level 2: Quarantine without preview
        if mode == "quarantine" and not preview:
            skip_key = settings.get("confirm_quarantine_skip", False)
            if not skip_key:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(t("clean.confirm_quarantine_title"))
                msg_box.setText(t("clean.confirm_quarantine_msg", count=selected_count))
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                cb = QCheckBox(t("clean.dont_ask_again"))
                msg_box.setCheckBox(cb)
                if msg_box.exec() == QMessageBox.StandardButton.Yes:
                    if cb.isChecked():
                        settings.set("confirm_quarantine_skip", True)
                    return True
                return False

        # Level 3: Large number of items (>50) regardless of mode
        if selected_count > 50 and not preview:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(t("clean.confirm_many_title"))
            msg_box.setText(t("clean.confirm_many_msg", count=selected_count))
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            return msg_box.exec() == QMessageBox.StandardButton.Yes

        return True

    def _done(self, payload):
        from ..core.reporter import diff_reports

        result, before_report, after_report = payload
        self.run_btn.setEnabled(True)
        self.run_btn.setText(t("clean.btn_exec"))
        self.progress_bar.setVisible(False)

        self.log_view.append(result.summary())
        for line in result.lines:
            self.log_view.append(line)

        if not result.preview:
            self.log_view.append(t("clean.before_after"))
            for line in diff_reports(before_report, after_report):
                self.log_view.append(line)

            self.mw.session_freed_bytes += result.freed_bytes
            self.mw.dashboard_view.refresh_stats()

            # Record stats
            try:
                from ..core.viral import get_stats
                get_stats().record_clean(result.removed_items, result.freed_bytes)
            except Exception:
                pass

            # Notification
            try:
                from ..core.notifications import notify_clean_complete
                notify_clean_complete(result.removed_items, result.freed_bytes)
            except Exception:
                pass

            # Update tree with post-scan sizes
            self._update_tree_sizes(after_report)

        self.log_view.append("")

    def _failed(self, message: str):
        self.run_btn.setEnabled(True)
        self.run_btn.setText(t("clean.btn_exec"))
        self.progress_bar.setVisible(False)

        # Better error dialog with retry
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(t("clean.error"))
        msg_box.setText(t("clean.error_occurred"))
        msg_box.setInformativeText(message)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        retry_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        retry_btn.setText(t("clean.retry"))
        msg_box.button(QMessageBox.StandardButton.No).setText(t("common.close"))

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            self.run_clean()

    def _update_tree_sizes(self, report):
        """Update tree items with actual sizes after scan."""
        entry_map = {e.target.id: e for e in report.entries}
        for target_id, item in self._tree_items.items():
            entry = entry_map.get(target_id)
            if entry and entry.total_bytes > 0:
                from ..utils.paths import fmt_bytes
                item.setText(1, fmt_bytes(entry.total_bytes))

    def _show_inline_error(self, message: str):
        """Show temporary inline error message."""
        if not hasattr(self, '_error_label'):
            self._error_label = QLabel()
            self._error_label.setObjectName("errorLabel")
            self._error_label.setStyleSheet("color: #EF5350; font-size: 13px;")
            # Insert before log_view
            parent_layout = self.layout()
            log_idx = parent_layout.indexOf(self.log_view)
            if log_idx >= 0:
                parent_layout.insertWidget(log_idx, self._error_label)
        self._error_label.setText(f"⚠ {message}")
        self._error_label.show()
        QTimer.singleShot(5000, self._error_label.hide)

    def _shake_widget(self, widget):
        """Shake animation for error feedback."""
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(400)
        anim.setEasingCurve(QEasingCurve.Type.OutElastic)
        orig = widget.pos()
        anim.setKeyValueAt(0, orig)
        anim.setKeyValueAt(0.1, orig + QPoint(10, 0))
        anim.setKeyValueAt(0.2, orig + QPoint(-10, 0))
        anim.setKeyValueAt(0.3, orig + QPoint(8, 0))
        anim.setKeyValueAt(0.4, orig + QPoint(-6, 0))
        anim.setKeyValueAt(0.5, orig + QPoint(4, 0))
        anim.setKeyValueAt(0.6, orig + QPoint(-2, 0))
        anim.setKeyValueAt(1, orig)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# Need os import for _open_item_location
import os