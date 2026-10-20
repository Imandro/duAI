"""Panic widget with reduced-motion support, hotkey confirmation, and accessibility."""

from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QRadioButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
    QButtonGroup, QGraphicsOpacityEffect, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut

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


def _reduced_motion_enabled() -> bool:
    """True si el usuario o el sistema piden menos animaciones.

    Se comprueba con hasattr porque QStyleHints no expone
    animationEnabled() en todas las versiones de PySide6/Qt.
    """
    try:
        if get_settings().get("theme.reduced_motion", False):
            return True
    except Exception:
        pass
    try:
        hints = QGuiApplication.styleHints()
        for attr in ("animationEnabled", "useAnimations"):
            if hasattr(hints, attr):
                return not bool(getattr(hints, attr)() if callable(getattr(hints, attr))
                                else getattr(hints, attr))
    except Exception:
        pass
    return False


class PanicWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        settings = get_settings()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)

        micro = QLabel(t("panic.response"))
        micro.setObjectName("microLabel")
        layout.addWidget(micro)

        title = QLabel(t("panic.mode"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; color: #FFFFFF;")
        layout.addWidget(title)

        caption = QLabel(t("panic.desc"))
        caption.setWordWrap(True)
        caption.setObjectName("heroBody")
        caption.setMaximumWidth(560)
        layout.addWidget(caption)

        # Panic button with enhanced styling
        self.panic_btn = QPushButton(t("panic.btn"))
        self.panic_btn.setObjectName("panicButton")
        self.panic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panic_btn.clicked.connect(self.trigger_panic)
        self.panic_btn.setAccessibleName(t("panic.btn"))
        self.panic_btn.setAccessibleDescription(t("panic.btn_desc"))
        self.panic_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.panic_btn)

        self._pulse = Pulsing(self.panic_btn, low=0.6, duration=1500)

        # Mode selection
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
            radio.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            radio.setToolTip(t(f"panic.mode_{value}_tooltip"))
            radio.setAccessibleName(label)
            radio.setAccessibleDescription(t(f"panic.mode_{value}_desc"))
            self.mode_group.addButton(radio)
            options.addWidget(radio)
        options.addStretch(1)
        layout.addLayout(options)

        # Auto-exit and interval
        auto_row = QHBoxLayout()
        self.auto_exit_check = QCheckBox(t("panic.auto_clean"))
        self.auto_exit_check.setChecked(bool(settings.get("auto_clean_on_exit")))
        self.auto_exit_check.toggled.connect(self._save_auto_exit)
        self.auto_exit_check.setToolTip(t("panic.auto_clean_tooltip"))
        self.auto_exit_check.setAccessibleName(t("panic.auto_clean"))
        self.auto_exit_check.setAccessibleDescription(t("panic.auto_clean_desc"))

        interval_label = QLabel(t("panic.interval"))
        interval_label.setObjectName("microLabel")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 1440)
        self.interval_spin.setValue(int(settings.get("auto_interval_min") or 0))
        self.interval_spin.valueChanged.connect(self._save_interval)
        self.interval_spin.setToolTip(t("panic.interval_tooltip"))
        self.interval_spin.setAccessibleName(t("panic.interval"))
        self.interval_spin.setAccessibleDescription(t("panic.interval_desc"))

        hotkey_label = QLabel(t("panic.hotkey"))
        hotkey_label.setObjectName("microLabel")
        self.hotkey_check = QCheckBox(t("panic.hotkey_active"))
        self.hotkey_check.setChecked(bool(settings.get("hotkey_enabled", False)))  # Default False
        self.hotkey_check.toggled.connect(self._save_hotkey)
        self.hotkey_check.setToolTip(t("panic.hotkey_tooltip"))
        self.hotkey_check.setAccessibleName(t("panic.hotkey"))
        self.hotkey_check.setAccessibleDescription(t("panic.hotkey_desc"))

        auto_row.addWidget(self.auto_exit_check)
        auto_row.addStretch(1)
        auto_row.addWidget(interval_label)
        auto_row.addWidget(self.interval_spin)
        auto_row.addStretch(1)
        auto_row.addWidget(hotkey_label)
        auto_row.addWidget(self.hotkey_check)
        layout.addLayout(auto_row)

        # Float widget settings
        widget_row = QHBoxLayout()
        float_label = QLabel(t("panic.float"))
        float_label.setObjectName("microLabel")
        self.float_check = QCheckBox(t("panic.float_show"))
        self.float_check.setChecked(bool(settings.get("float_visible")))
        self.float_check.toggled.connect(self._save_float)
        self.float_check.setToolTip(t("panic.float_tooltip"))
        self.float_check.setAccessibleName(t("panic.float"))
        self.float_check.setAccessibleDescription(t("panic.float_desc"))

        size_label = QLabel(t("panic.float_size"))
        size_label.setObjectName("microLabel")
        self.float_size = QSpinBox()
        self.float_size.setRange(80, 300)
        self.float_size.setSingleStep(10)
        self.float_size.setValue(settings.get("float_size") or 132)
        self.float_size.setSuffix(" px")
        self.float_size.valueChanged.connect(self._save_float_size)
        self.float_size.setToolTip(t("panic.float_size_tooltip"))
        self.float_size.setAccessibleName(t("panic.float_size"))
        self.float_size.setAccessibleDescription(t("panic.float_size_desc"))

        widget_row.addWidget(float_label)
        widget_row.addWidget(self.float_check)
        widget_row.addStretch(1)
        widget_row.addWidget(size_label)
        widget_row.addWidget(self.float_size)
        layout.addLayout(widget_row)

        # Progress bar (shown during panic)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Result view
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setAccessibleName(t("panic.results"))
        self.result_view.setAccessibleDescription(t("panic.results_desc"))
        layout.addWidget(self.result_view, 1)

        layout.addWidget(self._hint())

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Hotkey confirmation toast
        self._hotkey_toast = None

        # Reduced motion check (user setting + system preference)
        self._reduced_motion = _reduced_motion_enabled()

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
        # Ctrl+Enter / Space - Trigger panic
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.trigger_panic)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.trigger_panic,
                  context=Qt.ShortcutContext.WidgetWithChildrenShortcut)

        # Arrow keys for mode navigation (handled by radio group)

        # Tooltip with shortcuts
        self.panic_btn.setToolTip(f"{t('panic.btn')} (Ctrl+Enter / Space)")
        for radio in self.mode_group.buttons():
            radio.setToolTip(radio.toolTip() + " (Arrow keys to navigate)")

    def _hint(self):
        hint = QLabel(t("panic.admin_note"))
        hint.setObjectName("statusLabel")
        return hint

    def showEvent(self, event):
        super().showEvent(event)
        # Respect reduced motion preference
        if self._reduced_motion:
            self._pulse.stop()
        elif self._worker is None or not self._worker.isRunning():
            self._pulse.start()

        # Update reduced motion state in case it changed
        self._reduced_motion = _reduced_motion_enabled()

    def hideEvent(self, event):
        self._pulse.stop()
        super().hideEvent(event)

    def trigger_panic(self):
        if self._worker and self._worker.isRunning():
            return False

        # Get selected mode
        mode = next(
            (radio.property("mode") for radio in self.mode_group.buttons() if radio.isChecked()),
            "recycle",
        )

        # Mode-specific confirmation
        if not self._confirm_panic(mode):
            return False

        self._pulse.stop()
        self.panic_btn.setEnabled(False)
        self.panic_btn.setText(t("panic.cleaning"))
        self.progress_bar.setVisible(True)

        def job():
            return perform_panic(mode=mode)

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()
        return True

    def _confirm_panic(self, mode: str) -> bool:
        """Enhanced confirmation with mode-specific warnings."""
        from ..utils.settings import get_settings

        settings = get_settings()
        skip_key = f"panic_confirm_skip_{mode}"
        if settings.get(skip_key, False):
            return True

        # Mode-specific messages
        messages = {
            "permanent": t("panic.confirm_permanent_msg"),
            "quarantine": t("panic.confirm_quarantine_msg"),
            "recycle": t("panic.confirm_recycle_msg"),
        }

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(t("panic.confirm_title"))
        msg_box.setText(messages.get(mode, t("panic.confirm_msg", mode=mode)))
        msg_box.setIcon(QMessageBox.Icon.Critical if mode == "permanent" else QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        cb = QCheckBox(t("panic.dont_ask_again"))
        msg_box.setCheckBox(cb)

        result = msg_box.exec()
        confirmed = result == QMessageBox.StandardButton.Yes

        if cb.isChecked() and confirmed:
            settings.set(skip_key, True)

        return confirmed

    def _done(self, result):
        self.panic_btn.setEnabled(True)
        self.panic_btn.setText(t("panic.btn"))
        self._pulse.start()
        self.progress_bar.setVisible(False)

        self.result_view.setPlainText(format_result_summary(result))

        try:
            from ..core.notifications import notify_panic_complete
            notify_panic_complete()
        except Exception:
            pass

        self.mw.session_freed_bytes += result.freed_bytes
        self.mw.dashboard_view.refresh_stats()

        try:
            from ..core.viral import get_stats
            get_stats().record_panic()
        except Exception:
            pass

        # Announce completion for screen readers
        self._announce(t("panic.completed", items=result.removed_items))

    def _failed(self, message: str):
        self.panic_btn.setEnabled(True)
        self.panic_btn.setText(t("panic.btn"))
        self._pulse.start()
        self.progress_bar.setVisible(False)

        # Error recovery dialog with retry option
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(t("panic.error"))
        msg_box.setText(t("panic.error_occurred"))
        msg_box.setInformativeText(message)
        msg_box.setIcon(QMessageBox.Icon.Critical)

        retry_btn = msg_box.addButton(t("panic.retry"), QMessageBox.ButtonRole.ActionRole)
        close_btn = msg_box.addButton(QMessageBox.StandardButton.Close)

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            self.trigger_panic()

    def _announce(self, message: str):
        """Announce to screen readers."""
        from PySide6.QtGui import QAccessible
        QAccessible.updateAccessibility(self, QAccessible.Event.Alert)
        # Also update a status label if we had one
        self.result_view.setToolTip(message)

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
        # Show confirmation toast
        if state:
            self._show_hotkey_toast(t("panic.hotkey_enabled_toast"))
        else:
            self._show_hotkey_toast(t("panic.hotkey_disabled_toast"))

    def _show_hotkey_toast(self, message: str):
        """Show temporary toast notification for hotkey changes."""
        if self._hotkey_toast:
            self._hotkey_toast.deleteLater()

        self._hotkey_toast = QLabel(message)
        self._hotkey_toast.setObjectName("toastLabel")
        self._hotkey_toast.setStyleSheet("""
            QLabel#toastLabel {
                background: rgba(0, 0, 0, 0.9);
                color: #FFFFFF;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 13px;
            }
        """)
        self._hotkey_toast.setParent(self)
        self._hotkey_toast.move(self.width() // 2 - self._hotkey_toast.width() // 2, 80)
        self._hotkey_toast.show()

        # Fade out animation
        effect = QGraphicsOpacityEffect()
        self._hotkey_toast.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(2500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self._hotkey_toast.deleteLater)
        anim.start()

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