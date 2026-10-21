"""Viral view with tiered achievements, progress rings, enhanced sharing, and viral mechanics."""

from PySide6.QtCore import (QUrl, Qt, QTimer, QRect, QRectF, QPropertyAnimation,
                            QEasingCurve)
from PySide6.QtGui import QDesktopServices, QPainter, QPen, QColor, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget, QFrame, QComboBox, QDialog, QDialogButtonBox,
    QLineEdit
)

from ..core.viral import (
    get_stats,
    generate_share_report,
    copy_to_clipboard,
    open_share_url,
)
from ..core.streak import get_streak
from ..core.privacy_score import get_latest_score
from ..i18n import t
from ..utils.settings import get_settings
from ..utils.paths import fmt_bytes
from .animations import count_to, fade_in, fade_out


class CircularProgressBar(QWidget):
    """Circular progress bar for achievement progress."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._color = QColor("#FFD700")
        self.setFixedSize(56, 56)

    def set_progress(self, value: float):
        self._progress = max(0.0, min(1.0, value))
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)

        # Background ring
        bg_pen = QPen(QColor("#333333"), 4)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress ring
        if self._progress > 0:
            fg_pen = QPen(self._color, 4)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fg_pen)
            span = int(-self._progress * 360 * 16)  # negative = clockwise
            painter.drawArc(rect, 90 * 16, span)


class AchievementCard(QFrame):
    """Tarjeta de logro con animacion de entrada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = None

    def animate_entrance(self):
        """Animacion de entrada escalonada (fade + slide)."""
        fade_in(self, duration=320)

        # Slide up
        geo_anim = QPropertyAnimation(self, b"geometry")
        geo_anim.setDuration(320)
        geo_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        rect = self.geometry()
        geo_anim.setStartValue(QRect(rect.x(), rect.y() + 14, rect.width(), rect.height()))
        geo_anim.setEndValue(rect)
        geo_anim.start()


class ShareDialog(QDialog):
    """Enhanced share dialog with platform picker, preview, and templates."""
    def __init__(self, parent, default_report):
        super().__init__(parent)
        self.setWindowTitle(t("viral.share_title"))
        self.setModal(True)
        self.resize(480, 360)

        layout = QVBoxLayout(self)

        # Platform selector
        platform_row = QHBoxLayout()
        platform_row.addWidget(QLabel(t("viral.platform")))
        self.platform = QComboBox()
        self.platform.addItems(["Twitter/X", "LinkedIn", "Mastodon", "Bluesky", "Reddit", "Email", "Custom"])
        platform_row.addWidget(self.platform)
        layout.addLayout(platform_row)

        # Preview
        preview_label = QLabel(t("viral.preview"))
        preview_label.setObjectName("microLabel")
        layout.addWidget(preview_label)

        self.preview = QTextEdit()
        self.preview.setPlainText(default_report)
        self.preview.setReadOnly(False)
        layout.addWidget(self.preview, 1)

        # Template buttons
        template_row = QHBoxLayout()
        for tmpl_key in ["minimal", "detailed", "fun"]:
            btn = QPushButton(t(f"viral.template.{tmpl_key}"))
            btn.clicked.connect(lambda _, k=tmpl_key: self._apply_template(k))
            template_row.addWidget(btn)
        template_row.addStretch()
        layout.addLayout(template_row)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_template(self, key):
        latest = get_latest_score()
        streak = get_streak()
        stats = get_stats()
        templates = {
            "minimal": f"\U0001f6e1\ufe0f duAI Privacy Score: {{score}}/100\n#duAI #PrivacyFirst",
            "detailed": generate_share_report(),
            "fun": f"Just cleaned {{freed}} of trackers with duAI! \U0001f680\nStreak: {{streak}} days \U0001f525\n#duAI #Privacy",
        }
        self.preview.setPlainText(templates[key].format(
            score=latest.get("score", 50) if latest else 50,
            freed=fmt_bytes(stats.get("total_freed_bytes", 0)),
            streak=streak.get("current", 0),
        ))

    def get_selection(self):
        return self.platform.currentText().lower().replace("/", ""), self.preview.toPlainText()


class ViralView(QWidget):
    """Pantalla de logros (gamificacion) y reporte para compartir en redes."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.stats = get_stats()
        self._animations = []

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("viral.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)

        title = QLabel(t("viral.achievements"))
        title.setStyleSheet("font-size: 22px; font-weight: 300; letter-spacing: 2px; color: #FFFFFF;")
        outer.addWidget(title)

        # Achievements scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.ach_layout = QVBoxLayout(content)
        self.ach_layout.setContentsMargins(0, 0, 16, 0)
        self.ach_layout.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Statistics with animated counters
        stats_box = QFrame()
        stats_box.setObjectName("statCard")
        stats_layout = QVBoxLayout(stats_box)
        stats_layout.setContentsMargins(16, 16, 16, 16)
        stats_layout.setSpacing(8)

        stat_title = QLabel(t("viral.stats"))
        stat_title.setObjectName("microLabel")
        stats_layout.addWidget(stat_title)

        self.stat_scans = self._stat_row(stats_layout, t("viral.scans"), "0")
        self.stat_cleans = self._stat_row(stats_layout, t("viral.cleans"), "0")
        self.stat_panics = self._stat_row(stats_layout, t("viral.panics"), "0")
        self.stat_freed = self._stat_row(stats_layout, t("viral.freed"), "0 B")
        self.stat_score = self._stat_row(stats_layout, "PRIVACY SCORE", "\u2014")
        # Fixed: removed duplicate stat_streak, use proper streak with fire emoji
        self.stat_streak = self._stat_row(stats_layout, t("viral.streak"), "0 \U0001f525")
        outer.addWidget(stats_box)

        # Referral / Invite section
        invite_box = QFrame()
        invite_box.setObjectName("inviteCard")
        invite_layout = QVBoxLayout(invite_box)
        invite_layout.setContentsMargins(16, 16, 16, 16)

        invite_title = QLabel(t("viral.invite_title"))
        invite_title.setObjectName("microLabel")
        invite_layout.addWidget(invite_title)

        # Referral code display
        ref_row = QHBoxLayout()
        self.ref_code = QLabel(self.stats.get_referral_code() or "\u2014")
        self.ref_code.setObjectName("refCode")
        self.ref_code.setStyleSheet("font-family: monospace; font-size: 18px; letter-spacing: 2px; color: #FFD700;")
        ref_row.addWidget(self.ref_code)
        copy_ref = QPushButton(t("viral.copy_ref"))
        copy_ref.setObjectName("iconBtn")
        copy_ref.clicked.connect(self._copy_referral)
        ref_row.addWidget(copy_ref)
        invite_layout.addLayout(ref_row)

        # Share streak
        self.streak_info = QLabel(t("viral.share_streak", count=self.stats.get("share_streak", 0)))
        self.streak_info.setObjectName("streakInfo")
        invite_layout.addWidget(self.streak_info)

        outer.addWidget(invite_box)

        # Share actions
        share_row = QHBoxLayout()
        self.share_btn = QPushButton(t("viral.share"))
        self.share_btn.setObjectName("shareBtn")
        self.share_btn.clicked.connect(self._share)
        copy_btn = QPushButton(t("viral.copy_report"))
        copy_btn.clicked.connect(self._copy_report)
        report_img_btn = QPushButton(t("viral.save_png"))
        report_img_btn.clicked.connect(self._save_report_image)
        share_row.addWidget(self.share_btn)
        share_row.addWidget(copy_btn)
        share_row.addWidget(report_img_btn)
        share_row.addStretch(1)
        outer.addLayout(share_row)

        # Botones de compartir directa por plataforma (abren el navegador predeterminado
        # con el reporte de privacidad preformateado, sin datos sensibles)
        platform_row = QHBoxLayout()
        platform_label = QLabel(t("viral.share_platform"))
        platform_label.setObjectName("microLabel")
        platform_row.addWidget(platform_label)
        for platform, key in [
            ("twitter", "viral.share_twitter"),
            ("telegram", "viral.share_telegram"),
            ("whatsapp", "viral.share_whatsapp"),
            ("facebook", "viral.share_facebook"),
        ]:
            btn = QPushButton(t(key))
            btn.setObjectName("sharePlatformBtn")
            btn.clicked.connect(lambda _, p=platform: self._share_platform(p))
            platform_row.addWidget(btn)
        platform_row.addStretch(1)
        outer.addLayout(platform_row)

        hint = QLabel(t("viral.report_title"))
        hint.setObjectName("shareHint")
        outer.addWidget(hint)

        # Keyboard shortcuts
        self._setup_shortcuts()

        self.refresh()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._share)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self._copy_report)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._save_report_image)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.ref_code.setFocus())

        self.share_btn.setToolTip(f"{t('viral.share')} (Ctrl+S)")
        copy_btn = self.findChild(QPushButton, "copyBtn")
        if not copy_btn:
            # Find the copy button
            for btn in self.findChildren(QPushButton):
                if t("viral.copy_report") in btn.text():
                    btn.setToolTip(f"{t('viral.copy_report')} (Ctrl+C)")
                    break

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
        # Clear with fade animation
        self._clear_achievements_animated()

        achievements = self.stats.unlocked_achievements()
        all_achievements = self.stats.get_all_achievements()  # Includes locked with progress

        if not all_achievements:
            empty = QLabel(t("viral.no_achievements"))
            empty.setObjectName("statusLabel")
            self.ach_layout.addWidget(empty)
            return

        for i, ach in enumerate(all_achievements):
            card = self._create_achievement_card(ach)
            self.ach_layout.addWidget(card)
            # Staggered entrance animation
            QTimer.singleShot(50 * i, card.animate_entrance)

        # Update animated stats
        self._animate_stats()

    def _clear_achievements_animated(self):
        """Fade out existing achievements before clearing."""
        for i in range(self.ach_layout.count()):
            child = self.ach_layout.itemAt(i)
            if child and child.widget():
                widget = child.widget()
                fade_out(widget, duration=150, on_finished=lambda w=widget: w.deleteLater())
                self._animations.append(widget)
        # Actually remove after animations
        QTimer.singleShot(200, lambda: self._do_clear_layout())

    def _do_clear_layout(self):
        while self.ach_layout.count():
            child = self.ach_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _create_achievement_card(self, ach: dict) -> QFrame:
        frame = AchievementCard()
        frame.setObjectName("achievementCard")
        frame.setProperty("tier", ach.get("tier", "bronze"))
        frame.setProperty("unlocked", ach["unlocked"])

        tier_colors = {
            "bronze": "#CD7F32",
            "silver": "#C0C0C0",
            "gold": "#FFD700",
            "platinum": "#E5E4E2",
        }
        color = tier_colors.get(ach.get("tier", "bronze"), "#CD7F32")
        opacity = "1.0" if ach["unlocked"] else "0.5"
        frame.setStyleSheet(f"""
            QFrame#achievementCard {{
                border: 2px solid {color};
                border-radius: 12px;
                background: rgba({self._hex_to_rgb(color)}, 0.1);
                opacity: {opacity};
            }}
            QFrame#achievementCard[unlocked="true"] {{ background: rgba({self._hex_to_rgb(color)}, 0.15); }}
            QLabel#achName {{ font-size: 14px; font-weight: 600; color: #FFFFFF; }}
            QLabel#achDesc {{ font-size: 12px; color: #CCCCCC; }}
            QLabel#achProgress {{ font-size: 11px; color: {color}; }}
            QLabel#tierBadge {{ font-size: 10px; font-weight: 700; color: {color}; padding: 4px 8px; border-radius: 4px; background: rgba({self._hex_to_rgb(color)}, 0.2); }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Icon with progress ring for locked achievements
        icon_container = QWidget()
        icon_container.setFixedSize(56, 56)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel(ach.get("icon", "\U0001f3c6"))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        icon_layout.addWidget(icon)

        if not ach["unlocked"]:
            progress = CircularProgressBar()
            progress.setFixedSize(56, 56)
            progress.set_progress(ach.get("progress", 0) / max(1, ach.get("target", 1)))
            progress.set_color(color)
            progress.setStyleSheet("background: transparent;")
            icon_layout.addWidget(progress)

        layout.addWidget(icon_container)

        # Info column
        info = QVBoxLayout()
        info.setSpacing(4)
        name = QLabel(ach["name"])
        name.setObjectName("achName")
        info.addWidget(name)

        desc = QLabel(ach["desc"])
        desc.setObjectName("achDesc")
        desc.setWordWrap(True)
        info.addWidget(desc)

        if not ach["unlocked"]:
            progress_text = QLabel(f"{ach.get('progress', 0)}/{ach.get('target', 1)} {ach.get('unit', '')}")
            progress_text.setObjectName("achProgress")
            info.addWidget(progress_text)
        else:
            unlocked_at = QLabel(f"\U0001f513 {ach.get('unlocked_at', '')}")
            unlocked_at.setObjectName("achUnlockedAt")
            info.addWidget(unlocked_at)

        layout.addLayout(info, 1)

        # Tier badge
        tier_badge = QLabel(ach.get("tier", "").upper())
        tier_badge.setObjectName("tierBadge")
        tier_badge.setProperty("tier", ach.get("tier", "bronze"))
        layout.addWidget(tier_badge)

        # Share button per achievement
        if ach["unlocked"]:
            share_one = QPushButton("\U0001f4e4")
            share_one.setObjectName("iconBtn")
            share_one.setToolTip(t("viral.share_achievement"))
            share_one.clicked.connect(lambda _, a=ach: self._share_single_achievement(a))
            layout.addWidget(share_one)

        return frame

    def _hex_to_rgb(self, hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        return ", ".join(str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4))

    def _animate_stats(self):
        count_to(self.stat_scans, self.stats.get("scans", 0), formatter=str)
        count_to(self.stat_cleans, self.stats.get("cleans", 0), formatter=str)
        count_to(self.stat_panics, self.stats.get("panics", 0), formatter=str)
        count_to(self.stat_freed, self.stats.get("total_freed_bytes", 0), formatter=fmt_bytes)
        latest = get_latest_score()
        if latest:
            self.stat_score.setText(str(latest.get("score", "\u2014")))
        streak = get_streak()
        self.stat_streak.setText(f"{streak.get('current', 0)} \U0001f525")

    def _share(self):
        dialog = ShareDialog(self, generate_share_report())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            platform, custom_text = dialog.get_selection()
            report = custom_text or generate_share_report()
            url = open_share_url(platform, report)
            QDesktopServices.openUrl(QUrl(url))
            self._track_share_event(platform)

    def _share_single_achievement(self, ach: dict):
        """Share a single achievement."""
        text = f"\U0001f3c6 {ach['name']} unlocked! {ach['desc']}\n#duAI #Achievement"
        url = open_share_url("twitter", text)
        QDesktopServices.openUrl(QUrl(url))
        self._track_share_event("twitter")

    def _share_platform(self, platform: str):
        """Comparte el reporte de privacidad en una plataforma mediante el navegador predeterminado."""
        report = generate_share_report()  # reporte sin datos sensibles
        url = open_share_url(platform, report)
        QDesktopServices.openUrl(QUrl(url))
        self._track_share_event(platform)
        self.mw.cli_output(t("viral.shared_to", platform=platform.title()))

    def _track_share_event(self, platform: str):
        """Track share for viral mechanics."""
        self.stats.increment("share_streak")
        self.streak_info.setText(t("viral.share_streak", count=self.stats.get("share_streak", 0)))

    def _copy_referral(self):
        if copy_to_clipboard(self.stats.get_referral_code()):
            self.mw.cli_output(t("viral.ref_copied"))

    def _copy_report(self):
        report = generate_share_report()
        if copy_to_clipboard(report):
            self.mw.cli_output(t("viral.copied"))
        else:
            self.mw.cli_output(t("viral.copy_failed"))

    def _save_report_image(self):
        from ..core.report_image import generate_and_open

        latest = get_latest_score()
        score = latest["score"] if latest else 50
        stats = get_stats()
        streak = get_streak()

        path = generate_and_open(
            score=score,
            found_count=stats.get("total_found", 0),
            freed_bytes=stats.get("total_freed_bytes", 0),
            streak_days=streak.get("current", 0),
            achievements_unlocked=len(stats.unlocked_achievements()),
        )
        self.mw.cli_output(t("viral.saved_png", path=path))