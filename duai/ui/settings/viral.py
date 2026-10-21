"""Pestaña Viral de ajustes (gamificacion, leaderboard, compartir, desafios).

Extraido de duai/ui/settings_view.py. API: ViralTab(main_window) -> QWidget
con atributo .scroll (QScrollArea).
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QFrame,
)

from duai.core.leaderboard import get_user_rank, is_leaderboard_enabled, set_leaderboard_enabled
from duai.core.viral import reset_stats, set_gamification
from duai.i18n import t
from duai.utils.settings import get_settings
from .base import SettingsTab


class ViralTab(SettingsTab):
    """Pestaña Viral."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.scroll, layout = self._create_scroll_content()
        self._build_gamification(layout)
        self._build_leaderboard(layout)
        self._build_sharing(layout)
        self._build_challenges(layout)
        layout.addStretch(1)

    # ---------- gamificacion ----------
    def _build_gamification(self, layout):
        box = self._section(layout, t("viral.gamification"))

        self.gam_check = QCheckBox(t("viral.stats"))
        self.gam_check.setChecked(bool(get_settings().get("gamification", True)))
        self.gam_check.toggled.connect(
            lambda state: set_gamification(bool(state))
        )
        box.addWidget(self.gam_check)

        hint = QLabel(t("viral.gamification_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

        # Reset stats
        reset_btn = QPushButton(t("viral.reset_stats"))
        reset_btn.clicked.connect(self._reset_stats)
        box.addWidget(reset_btn)

    def _reset_stats(self):
        confirm = QMessageBox.question(
            self, "duAI", t("viral.reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            reset_stats()
            QMessageBox.information(self, "duAI", t("viral.reset_done"))
            self.mw.refresh_settings_page()

    # ---------- leaderboard ----------
    def _build_leaderboard(self, layout):
        box = self._section(layout, t("viral.leaderboard"))

        enabled = is_leaderboard_enabled()
        self.lb_check = QCheckBox(t("viral.leaderboard_enable"))
        self.lb_check.setChecked(enabled)
        self.lb_check.toggled.connect(lambda state: set_leaderboard_enabled(bool(state)))
        box.addWidget(self.lb_check)

        # Show current rank
        if enabled:
            rank_info = get_user_rank()
            rank_text = t("viral.your_rank", rank=rank_info['rank'], total=rank_info['total'],
                          percentile=rank_info['percentile'], tier=rank_info['tier'].capitalize())
            rank_label = QLabel(rank_text)
            rank_label.setObjectName("heroBody")
            rank_label.setWordWrap(True)
            box.addWidget(rank_label)

            refresh_btn = QPushButton(t("viral.refresh_rank"))
            refresh_btn.clicked.connect(lambda: self.mw.refresh_settings_page())
            box.addWidget(refresh_btn)

        hint = QLabel(t("viral.leaderboard_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)

    # ---------- compartir ----------
    def _build_sharing(self, layout):
        box = self._section(layout, t("viral.sharing"))

        # Default share platform
        row = QHBoxLayout()
        lbl = QLabel(t("viral.default_platform"))
        lbl.setObjectName("microLabel")
        row.addWidget(lbl)

        self.share_combo = QComboBox()
        self.share_combo.addItems(["Twitter/X", "LinkedIn", "Mastodon", "Bluesky", "Reddit", "Email"])
        current = get_settings().get("share_platform") or "twitter"
        self.share_combo.setCurrentText(current.capitalize())
        self.share_combo.currentIndexChanged.connect(self._on_share_changed)
        row.addWidget(self.share_combo)
        row.addStretch(1)
        box.addLayout(row)

        # Auto-share after clean
        self.auto_share_check = QCheckBox(t("viral.auto_share"))
        self.auto_share_check.setChecked(get_settings().get("viral.auto_share", False))
        self.auto_share_check.toggled.connect(
            lambda state: get_settings().set("viral.auto_share", bool(state))
        )
        box.addWidget(self.auto_share_check)

    def _on_share_changed(self, index):
        platform = self.share_combo.currentText().lower()
        get_settings().set("share_platform", platform)

    # ---------- desafios ----------
    def _build_challenges(self, layout):
        box = self._section(layout, t("viral.challenges"))

        self.challenge_check = QCheckBox(t("viral.challenges_enable"))
        self.challenge_check.setChecked(get_settings().get("viral.challenges", True))
        self.challenge_check.toggled.connect(
            lambda state: get_settings().set("viral.challenges", bool(state))
        )
        box.addWidget(self.challenge_check)

        hint = QLabel(t("viral.challenges_hint"))
        hint.setObjectName("heroBody")
        hint.setWordWrap(True)
        box.addWidget(hint)
