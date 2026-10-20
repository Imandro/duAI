"""Dashboard view with animated score, streak, keyboard shortcuts, and accessibility."""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QRect
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QSizePolicy
)

from ..i18n import t
from ..utils.paths import fmt_bytes
from .animations import count_to


class DashboardView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._score_anim = None
        self._pulse_anim = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(14)

        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        import os, sys
        from .theme import current_mode
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(__file__), "..", "..")
        mode = current_mode()
        name = "duAI_white.png" if mode == "oscuro" else "duAI.png"
        for n in (name, "duAI.png"):
            icon_path = os.path.join(base, "assets", n)
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                logo_label.setPixmap(pixmap.scaled(227, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                break
        layout.addWidget(logo_label)

        layout.addWidget(self._micro(t("dash.status")))
        title = QLabel(t("dash.hero"))
        title.setObjectName("heroTitle")
        layout.addWidget(title)

        body = QLabel(t("dash.body"))
        body.setObjectName("heroBody")
        body.setWordWrap(True)
        body.setMaximumWidth(560)
        layout.addWidget(body)
        layout.addSpacing(24)

        # Privacy Score (grande, centrado)
        self.score_frame = QFrame()
        self.score_frame.setObjectName("scoreFrame")
        self.score_frame.setMinimumWidth(280)
        self.score_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        score_layout = QVBoxLayout(self.score_frame)
        score_layout.setContentsMargins(24, 16, 24, 16)
        score_layout.setSpacing(4)
        score_micro = QLabel("PRIVACY SCORE")
        score_micro.setObjectName("microLabel")
        score_layout.addWidget(score_micro)
        self.score_value = QLabel("\u2014")
        self.score_value.setObjectName("statNumber")
        self.score_value.setStyleSheet("font-size: 48px; font-weight: 700; color: #FFFFFF;")
        self.score_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.score_value)
        self.score_label = QLabel(t("dash.score_empty_hint"))
        self.score_label.setObjectName("statusLabel")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.score_label)
        layout.addWidget(self.score_frame)

        # Stats frame
        self.stats_frame = QFrame()
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(16)  # Reduced for responsiveness

        self.stat_traces = self._stat(stats_layout, t("dash.traces"), "0")
        self.stat_size = self._stat(stats_layout, t("dash.risk"), "0 B")
        self.stat_freed = self._stat(stats_layout, t("dash.freed"), "0 B")
        self.stat_last = self._stat(stats_layout, t("dash.last_scan"), t("dash.never"))
        layout.addWidget(self.stats_frame)

        # Streak display with enhanced visuals
        self.streak_frame = QFrame()
        self.streak_frame.setObjectName("statCard")
        streak_layout = QHBoxLayout(self.streak_frame)
        streak_layout.setContentsMargins(24, 12, 24, 12)
        streak_layout.setSpacing(16)
        self.streak_emoji = QLabel("\U0001f525")  # Fire emoji
        self.streak_emoji.setObjectName("microLabel")
        self.streak_emoji.setStyleSheet("font-size: 24px;")
        self.streak_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        streak_layout.addWidget(self.streak_emoji)
        streak_text = QVBoxLayout()
        streak_text.setSpacing(2)
        self.streak_title = QLabel(t("dash.streak_title"))
        self.streak_title.setObjectName("microLabel")
        streak_text.addWidget(self.streak_title)
        self.streak_value = QLabel("0 " + t("dash.days"))
        self.streak_value.setObjectName("statNumber")
        self.streak_value.setStyleSheet("font-size: 20px; font-weight: 700;")
        streak_text.addWidget(self.streak_value)
        self.streak_msg = QLabel(t("dash.streak_empty"))
        self.streak_msg.setObjectName("statusLabel")
        streak_text.addWidget(self.streak_msg)
        streak_layout.addLayout(streak_text)
        streak_layout.addStretch(1)
        layout.addWidget(self.streak_frame)

        layout.addSpacing(16)

        # Action buttons
        buttons = QHBoxLayout()
        self.scan_btn = QPushButton(t("dash.btn_scan"))
        self.scan_btn.setObjectName("scanBtn")
        self.scan_btn.clicked.connect(self._go_scan)
        self.scan_btn.setAccessibleName(t("dash.btn_scan"))
        self.scan_btn.setAccessibleDescription(t("dash.btn_scan_desc"))

        self.clean_btn = QPushButton(t("dash.btn_clean"))
        self.clean_btn.clicked.connect(lambda: self.mw.navigate(2))
        self.clean_btn.setAccessibleName(t("dash.btn_clean"))
        self.clean_btn.setAccessibleDescription(t("dash.btn_clean_desc"))

        self.quick_btn = QPushButton(t("dash.btn_quick"))
        self.quick_btn.setObjectName("shareBtn")
        self.quick_btn.clicked.connect(self._quick_clean)
        self.quick_btn.setAccessibleName(t("dash.btn_quick"))
        self.quick_btn.setAccessibleDescription(t("dash.btn_quick_desc"))

        buttons.addWidget(self.scan_btn)
        buttons.addWidget(self.clean_btn)
        buttons.addWidget(self.quick_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        # Initial streak load
        try:
            from ..core.streak import get_streak, get_streak_emoji, get_streak_message
            streak = get_streak()
            self.streak_emoji.setText(get_streak_emoji())
            self.streak_value.setText(f"{streak.get('current', 0)} {t('dash.days')}")
            self.streak_msg.setText(get_streak_message())
        except Exception:
            pass

        layout.addStretch(1)

        footer = QLabel(t("dash.footer"))
        footer.setObjectName("statusLabel")
        layout.addWidget(footer)

        # Keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._go_scan)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self._quick_clean)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: self.mw.navigate(2))

        # Tooltips with shortcuts
        self.scan_btn.setToolTip(f"{t('dash.btn_scan')} (Ctrl+S)")
        self.clean_btn.setToolTip(f"{t('dash.btn_clean')} (Ctrl+L)")
        self.quick_btn.setToolTip(f"{t('dash.btn_quick')} (Ctrl+Q)")

    def _micro(self, text):
        label = QLabel(text)
        label.setObjectName("microLabel")
        return label

    def _stat(self, parent_layout, caption, initial):
        box = QVBoxLayout()
        box.setSpacing(4)
        caption_label = QLabel(caption)
        caption_label.setObjectName("microLabel")
        value = QLabel(initial)
        value.setObjectName("statNumber")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(caption_label)
        box.addWidget(value)
        card = QWidget()
        card.setObjectName("statCard")
        card.setLayout(box)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumWidth(140)
        parent_layout.addWidget(card)
        return value

    def _animate_score(self, target_value):
        """Smooth animated score counter with color transition."""
        if self._score_anim:
            self._score_anim.stop()

        current = int(self.score_value.text()) if self.score_value.text().isdigit() else 0

        self._score_anim = QPropertyAnimation(self.score_value, b"text")
        self._score_anim.setDuration(800)
        self._score_anim.setStartValue(current)
        self._score_anim.setEndValue(target_value)
        self._score_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._score_anim.start()

        # Color animation
        from ..core.privacy_score import score_color
        color_anim = QPropertyAnimation(self.score_value, b"styleSheet")
        color_anim.setDuration(800)
        current_color = self.score_value.styleSheet()
        if "color:" in current_color:
            import re
            match = re.search(r"color:\s*#([0-9A-Fa-f]{6})", current_color)
            if match:
                current_color = f"#{match.group(1)}"
            else:
                current_color = "#FFFFFF"
        else:
            current_color = "#FFFFFF"
        target_color = score_color(target_value)
        color_anim.setStartValue(f"font-size: 48px; font-weight: 700; color: {current_color};")
        color_anim.setEndValue(f"font-size: 48px; font-weight: 700; color: {target_color};")
        color_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        color_anim.start()

    def _pulse_scan_button(self):
        """Pulse animation on scan button when score is empty."""
        if self._pulse_anim:
            self._pulse_anim.stop()

        self._pulse_anim = QPropertyAnimation(self.scan_btn, b"styleSheet")
        self._pulse_anim.setDuration(2000)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setKeyValueAt(0, "background-color: #3B82F6;")
        self._pulse_anim.setKeyValueAt(0.5, "background-color: #60A5FA;")
        self._pulse_anim.setKeyValueAt(1, "background-color: #3B82F6;")
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse_anim.start()

    def _animate_streak_update(self, new_streak):
        """Animate streak value with scale and color."""
        from ..core.streak import get_streak_emoji

        # Scale animation
        anim = QPropertyAnimation(self.streak_value, b"geometry")
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        rect = self.streak_value.geometry()
        anim.setStartValue(QRect(rect.x(), rect.y(), rect.width(), rect.height()))
        anim.setKeyValueAt(0.3, QRect(rect.x() - 5, rect.y() - 5, rect.width() + 10, rect.height() + 10))
        anim.setEndValue(rect)
        anim.start()

        # Color based on streak length
        colors = {0: "#6B7280", 1: "#3B82F6", 3: "#F59E0B", 7: "#EF4444", 14: "#8B5CF6"}
        for days, color in sorted(colors.items()):
            if new_streak >= days:
                self.streak_value.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")

        # Update emoji
        self.streak_emoji.setText(get_streak_emoji())

    def _setup_empty_score_state(self):
        """Set up empty state with pulse on scan button."""
        self.score_value.setText("\u2014")
        self.score_value.setStyleSheet("font-size: 48px; font-weight: 700; color: #FFFFFF;")
        self.score_label.setText(t("dash.score_empty_hint"))
        self._pulse_scan_button()

    def refresh_stats(self):
        report = getattr(self.mw, "last_report", None)
        if report is not None:
            found = len(report.found_entries)
            count_to(self.stat_traces, found, formatter=str)
            self.stat_size.setText(fmt_bytes(report.total_bytes))
            self.stat_last.setText(report.scanned_at)

            # Update Privacy Score with animation
            try:
                from ..core.privacy_score import calculate_score, score_label, score_color
                score = calculate_score(report)
                self._animate_score(score)
                self.score_label.setText(score_label(score))

                # Save to history
                from ..core.privacy_score import record_score
                record_score(score, report)

                # Update streak
                from ..core.streak import update_streak, get_streak_emoji, get_streak_message
                streak = update_streak(found)
                self._animate_streak_update(streak.get('current', 0))
                self.streak_msg.setText(get_streak_message())

                # Stop pulse animation if it was running
                if self._pulse_anim:
                    self._pulse_anim.stop()
            except Exception:
                pass
        else:
            self._setup_empty_score_state()

        freed = getattr(self.mw, "session_freed_bytes", 0)
        count_to(self.stat_freed, freed, formatter=fmt_bytes)

    def _quick_clean(self):
        from ..core.quick_clean import run_quick_clean
        from ..core.notifications import notify_clean_complete
        from PySide6.QtWidgets import QMessageBox

        confirm = QMessageBox.question(
            self, "duAI",
            t("dash.quick_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.mw.cli_output(t("dash.quick_starting"))
        from ..ui.worker import Worker

        def job():
            return run_quick_clean()

        def done(result):
            self.mw.session_freed_bytes += result["freed_bytes"]
            self.mw.last_report = result["report"]
            self.refresh_stats()
            self.mw.cli_output(t("dash.quick_done", cleaned=result['cleaned'], freed=fmt_bytes(result['freed_bytes'])))
            notify_clean_complete(result["cleaned"], result["freed_bytes"])

        worker = Worker(job)
        worker.done.connect(done)
        worker.failed.connect(lambda m: self.mw.cli_output(t("dash.quick_error", error=m)))
        worker.setParent(self.mw)
        worker.start()

    def _go_scan(self):
        self.mw.navigate(1)
        self.mw.scan_view.start_scan()

    def resizeEvent(self, event):
        """Handle responsive layout changes."""
        super().resizeEvent(event)
        width = event.size().width()
        stats_layout = self.stats_frame.layout()
        if stats_layout:
            if width < 700:
                stats_layout.setDirection(QHBoxLayout.Direction.TopToBottom)
            else:
                stats_layout.setDirection(QHBoxLayout.Direction.LeftToRight)