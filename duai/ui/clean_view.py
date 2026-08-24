from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
    QFrame,
)

from ..core.cleaner import CleanOptions, run_clean
from ..i18n import t
from .worker import Worker


class CleanView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        self._checkboxes = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("clean.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)

        header = QHBoxLayout()
        title = QLabel(t("clean.subtitle"))
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        header.addWidget(title)
        header.addStretch(1)
        self.run_btn = QPushButton(t("clean.btn_exec"))
        self.run_btn.clicked.connect(self.run_clean)
        header.addWidget(self.run_btn)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.groups_layout = QVBoxLayout(content)
        self.groups_layout.setContentsMargins(0, 0, 16, 0)
        self.groups_layout.setSpacing(20)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        options_row = QHBoxLayout()
        self.preview_check = QCheckBox(t("clean.preview"))
        self.preview_check.setChecked(True)
        self.recycle_radio = QRadioButton(t("clean.mode_recycle"))
        self.recycle_radio.setChecked(True)
        self.quarantine_radio = QRadioButton(t("clean.mode_quarantine"))
        self.permanent_radio = QRadioButton(t("clean.mode_permanent"))
        mode_group = QButtonGroup(self)
        for radio in (self.recycle_radio, self.quarantine_radio, self.permanent_radio):
            mode_group.addButton(radio)
        select_all = QPushButton(t("clean.select_all"))
        select_all.clicked.connect(lambda: self._set_all(True))
        clear_all = QPushButton(t("clean.deselect_all"))
        clear_all.clicked.connect(lambda: self._set_all(False))
        options_row.addWidget(self.preview_check)
        options_row.addWidget(self.recycle_radio)
        options_row.addWidget(self.quarantine_radio)
        options_row.addWidget(self.permanent_radio)
        options_row.addStretch(1)
        options_row.addWidget(select_all)
        options_row.addWidget(clear_all)
        outer.addLayout(options_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(180)
        self.log_view.setPlaceholderText(t("clean.placeholder"))
        outer.addWidget(self.log_view)

        self._build_groups()

    def _build_groups(self):
        from ..core.targets import list_all_entries
        from ..utils.settings import get_settings

        exclusions = set(get_settings().get("exclusions") or [])
        entries = [e for e in list_all_entries() if e["id"] not in exclusions]
        categories = {}
        for entry in entries:
            categories.setdefault(entry["category"], []).append(entry)

        for category_name, items in categories.items():
            frame = QFrame()
            frame.setObjectName("sectionFrame")
            box = QVBoxLayout(frame)
            box.setContentsMargins(0, 14, 0, 6)
            box.setSpacing(8)
            label = QLabel(category_name.upper())
            label.setObjectName("microLabel")
            box.addWidget(label)
            row_wrap = QWidget()
            rows = QVBoxLayout(row_wrap)
            rows.setSpacing(4)
            for entry in items:
                check = QCheckBox(entry["name"])
                check.setChecked(False)
                self._checkboxes[entry["id"]] = check
                rows.addWidget(check)
            box.addWidget(row_wrap)
            self.groups_layout.addWidget(frame)
        self.groups_layout.addStretch(1)

    def apply_cli(self, target_ids, mode, confirm):
        mode_radio = {
            "recycle": self.recycle_radio,
            "quarantine": self.quarantine_radio,
            "permanent": self.permanent_radio,
        }.get(mode, self.recycle_radio)
        mode_radio.setChecked(True)
        for target_id, check in self._checkboxes.items():
            check.setChecked(target_id in target_ids)
        self.preview_check.setChecked(not confirm)
        if not any(c.isChecked() for c in self._checkboxes.values()):
            return False
        self.run_clean()
        return True

    def _set_all(self, state):
        for check in self._checkboxes.values():
            check.setChecked(state)

    def selected_ids(self):
        return {tid for tid, check in self._checkboxes.items() if check.isChecked()}

    def run_clean(self):
        if self._worker and self._worker.isRunning():
            return
        selected = self.selected_ids()
        if not selected:
            QMessageBox.information(self, "duAI", t("clean.select_target"))
            return
        if self.permanent_radio.isChecked():
            mode = "permanent"
        elif self.quarantine_radio.isChecked():
            mode = "quarantine"
        else:
            mode = "recycle"
        preview = self.preview_check.isChecked()
        self.run_btn.setEnabled(False)
        self.run_btn.setText(t("clean.processing"))

        def job():
            from ..core.scanner import scan_targets
            from ..core.targets import build_targets
            from ..utils.settings import get_settings

            exclusions = set(get_settings().get("exclusions") or [])
            targets = [
                t for t in build_targets(exclusions=exclusions) if t.id in selected
            ]
            before_report = scan_targets(targets)
            options = CleanOptions(
                selected=set(t.id for t in targets),
                mode=mode,
                preview=preview,
            )
            result = run_clean(before_report, options)
            after_report = scan_targets(targets)
            return result, before_report, after_report

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _done(self, payload):
        from ..core.reporter import diff_reports

        result, before_report, after_report = payload
        self.run_btn.setEnabled(True)
        self.run_btn.setText(t("clean.btn_exec"))
        self.log_view.append(result.summary())
        for line in result.lines:
            self.log_view.append(line)
        if not result.preview:
            self.log_view.append(t("clean.before_after"))
            for line in diff_reports(before_report, after_report):
                self.log_view.append(line)
            self.mw.session_freed_bytes += result.freed_bytes
            self.mw.dashboard_view.refresh_stats()
        self.log_view.append("")

    def _failed(self, message):
        self.run_btn.setEnabled(True)
        self.run_btn.setText(t("clean.btn_exec"))
        QMessageBox.warning(self, "duAI", t("clean.error") + message)
