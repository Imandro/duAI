from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from ..core.panic import format_result_summary, perform_panic
from ..i18n import t
from ..utils.settings import get_settings
from .animations import Pulsing
from .worker import Worker

MODES = [
    ("recycle", t("clean.mode_recycle")),
    ("quarantine", t("clean.mode_quarantine")),
    ("permanent", t("clean.mode_permanent")),
]


class PanicWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        settings = get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        micro = QLabel(t("panic.response"))
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        title = QLabel(t("panic.mode"))
        title.setStyleSheet("font-size: 22px; font-weight: 300;")
        layout.addWidget(title)

        caption = QLabel(t("panic.desc"))
        caption.setWordWrap(True)
        caption.setObjectName("heroBody")
        caption.setMaximumWidth(560)
        layout.addWidget(caption)

        self.panic_btn = QPushButton(t("panic.btn"))
        self.panic_btn.setObjectName("panicButton")
        self.panic_btn.setCursor(self.cursor())
        self.panic_btn.clicked.connect(self.trigger_panic)
        layout.addWidget(self.panic_btn)

        self._pulse = Pulsing(self.panic_btn, low=0.6, duration=1500)

        options = QHBoxLayout()
        mode_label = QLabel(t("panic.destination"))
        mode_label.setObjectName("microLabel")
        options.addWidget(mode_label)
        self.mode_group = QButtonGroup(self)
        current_mode = settings.get("panic_mode") or "recycle"
        for value, label in MODES:
            radio = QRadioButton(label)
            radio.setProperty("mode", value)
            radio.setChecked(current_mode == value)
            radio.toggled.connect(lambda state: state and self._save_mode())
            self.mode_group.addButton(radio)
            options.addWidget(radio)
        options.addStretch(1)
        layout.addLayout(options)

        auto_row = QHBoxLayout()
        self.auto_exit_check = QCheckBox(t("panic.auto_clean"))
        self.auto_exit_check.setChecked(bool(settings.get("auto_clean_on_exit")))
        self.auto_exit_check.toggled.connect(self._save_auto_exit)
        interval_label = QLabel(t("panic.interval"))
        interval_label.setObjectName("microLabel")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 1440)
        self.interval_spin.setValue(int(settings.get("auto_interval_min") or 0))
        self.interval_spin.valueChanged.connect(self._save_interval)
        hotkey_label = QLabel(t("panic.hotkey"))
        hotkey_label.setObjectName("microLabel")
        self.hotkey_check = QCheckBox(t("panic.hotkey_active"))
        self.hotkey_check.setChecked(bool(settings.get("hotkey_enabled", True)))
        self.hotkey_check.toggled.connect(self._save_hotkey)
        auto_row.addWidget(self.auto_exit_check)
        auto_row.addStretch(1)
        auto_row.addWidget(interval_label)
        auto_row.addWidget(self.interval_spin)
        auto_row.addStretch(1)
        auto_row.addWidget(hotkey_label)
        auto_row.addWidget(self.hotkey_check)
        layout.addLayout(auto_row)

        widget_row = QHBoxLayout()
        float_label = QLabel(t("panic.float"))
        float_label.setObjectName("microLabel")
        self.float_check = QCheckBox(t("panic.float_show"))
        self.float_check.setChecked(bool(settings.get("float_visible")))
        self.float_check.toggled.connect(self._save_float)
        size_label = QLabel(t("panic.float_size"))
        size_label.setObjectName("microLabel")
        self.float_size = QSpinBox()
        self.float_size.setRange(80, 300)
        self.float_size.setSingleStep(10)
        self.float_size.setValue(settings.get("float_size") or 132)
        self.float_size.setSuffix(" px")
        self.float_size.valueChanged.connect(self._save_float_size)
        widget_row.addWidget(float_label)
        widget_row.addWidget(self.float_check)
        widget_row.addStretch(1)
        widget_row.addWidget(size_label)
        widget_row.addWidget(self.float_size)
        layout.addLayout(widget_row)

        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        layout.addWidget(self.result_view, 1)
        layout.addWidget(self._hint())

    def _hint(self):
        hint = QLabel(t("panic.admin_note"))
        hint.setObjectName("statusLabel")
        return hint

    def showEvent(self, event):
        super().showEvent(event)
        if self._worker is None or not self._worker.isRunning():
            self._pulse.start()

    def hideEvent(self, event):
        self._pulse.stop()
        super().hideEvent(event)

    def trigger_panic(self):
        if self._worker and self._worker.isRunning():
            return False
        self._pulse.stop()
        mode = next(
            (radio.property("mode") for radio in self.mode_group.buttons() if radio.isChecked()),
            "recycle",
        )
        self.panic_btn.setEnabled(False)
        self.panic_btn.setText(t("panic.cleaning"))

        def job():
            return perform_panic(mode=mode)

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()
        return True

    def _done(self, result):
        self.panic_btn.setEnabled(True)
        self.panic_btn.setText(t("panic.btn"))
        self._pulse.start()
        self.result_view.setPlainText(format_result_summary(result))
        self.mw.session_freed_bytes += result.freed_bytes
        self.mw.dashboard_view.refresh_stats()

    def _failed(self, message):
        self.panic_btn.setEnabled(True)
        self.panic_btn.setText(t("panic.btn"))
        self._pulse.start()
        QMessageBox.warning(self, "duAI", t("panic.error") + message)

    def _save_mode(self):
        checked = next(r for r in self.mode_group.buttons() if r.isChecked())
        get_settings().set("panic_mode", checked.property("mode"))

    def _save_auto_exit(self, state):
        get_settings().set("auto_clean_on_exit", bool(state))

    def _save_interval(self, value):
        get_settings().set("auto_interval_min", int(value))
        self.mw.restart_auto_timer()

    def _save_hotkey(self, state):
        get_settings().set("hotkey_enabled", bool(state))
        self.mw.restart_hotkey()

    def _save_float(self, state):
        get_settings().set("float_visible", bool(state))
        if state:
            self.mw.show_panic_float()
        else:
            self.mw.hide_panic_float()

    def _save_float_size(self, value):
        get_settings().set("float_size", value)
        if self.mw._float_widget:
            self.mw._float_widget.setFixedSize(value, value)
