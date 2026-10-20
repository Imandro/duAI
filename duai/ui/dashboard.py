from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..utils.paths import fmt_bytes
from .animations import count_to


class DashboardView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(14)

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
        self.score_frame.setObjectName("statCard")
        score_layout = QVBoxLayout(self.score_frame)
        score_layout.setContentsMargins(24, 16, 24, 16)
        score_layout.setSpacing(4)
        score_micro = QLabel("PRIVACY SCORE")
        score_micro.setObjectName("microLabel")
        score_layout.addWidget(score_micro)
        self.score_value = QLabel("—")
        self.score_value.setObjectName("statNumber")
        self.score_value.setStyleSheet("font-size: 48px; font-weight: 700; color: #FFFFFF;")
        score_layout.addWidget(self.score_value)
        self.score_label = QLabel("Escanea para calcular")
        self.score_label.setObjectName("statusLabel")
        score_layout.addWidget(self.score_label)
        layout.addWidget(self.score_frame)

        self.stats_frame = QFrame()
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(48)

        self.stat_traces = self._stat(stats_layout, t("dash.traces"), "0")
        self.stat_size = self._stat(stats_layout, t("dash.risk"), "0 B")
        self.stat_freed = self._stat(stats_layout, t("dash.freed"), "0 B")
        self.stat_last = self._stat(stats_layout, t("dash.last_scan"), t("dash.never"))
        layout.addWidget(self.stats_frame)

        # Streak display
        self.streak_frame = QFrame()
        self.streak_frame.setObjectName("statCard")
        streak_layout = QHBoxLayout(self.streak_frame)
        streak_layout.setContentsMargins(24, 12, 24, 12)
        streak_layout.setSpacing(16)
        self.streak_emoji = QLabel("RACHA")
        self.streak_emoji.setObjectName("microLabel")
        self.streak_emoji.setStyleSheet("font-size: 12px; font-weight: 700;")
        streak_layout.addWidget(self.streak_emoji)
        streak_text = QVBoxLayout()
        streak_text.setSpacing(2)
        self.streak_title = QLabel("RACHA DE PRIVACIDAD")
        self.streak_title.setObjectName("microLabel")
        streak_text.addWidget(self.streak_title)
        self.streak_value = QLabel("0 dias")
        self.streak_value.setObjectName("statNumber")
        self.streak_value.setStyleSheet("font-size: 20px; font-weight: 700;")
        streak_text.addWidget(self.streak_value)
        self.streak_msg = QLabel("Escanea para empezar")
        self.streak_msg.setObjectName("statusLabel")
        streak_text.addWidget(self.streak_msg)
        streak_layout.addLayout(streak_text)
        streak_layout.addStretch(1)
        layout.addWidget(self.streak_frame)

        layout.addSpacing(16)
        buttons = QHBoxLayout()
        scan_btn = QPushButton(t("dash.btn_scan"))
        scan_btn.clicked.connect(self._go_scan)
        clean_btn = QPushButton(t("dash.btn_clean"))
        clean_btn.clicked.connect(lambda: self.mw.navigate(2))
        quick_btn = QPushButton("LIMPIEZA RAPIDA")
        quick_btn.setObjectName("shareBtn")
        quick_btn.clicked.connect(self._quick_clean)
        buttons.addWidget(scan_btn)
        buttons.addWidget(clean_btn)
        buttons.addWidget(quick_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        # Cargar racha inicial
        try:
            from ..core.streak import get_streak, get_streak_emoji, get_streak_message
            streak = get_streak()
            self.streak_emoji.setText(get_streak_emoji())
            self.streak_value.setText(f"{streak.get('current', 0)} dias")
            self.streak_msg.setText(get_streak_message())
        except Exception:
            pass

        layout.addStretch(1)

        footer = QLabel(t("dash.footer"))
        footer.setObjectName("statusLabel")
        layout.addWidget(footer)

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
        box.addWidget(caption_label)
        box.addWidget(value)
        card = QWidget()
        card.setObjectName("statCard")
        card.setLayout(box)
        parent_layout.addWidget(card)
        return value

    def refresh_stats(self):
        report = getattr(self.mw, "last_report", None)
        if report is not None:
            found = len(report.found_entries)
            count_to(self.stat_traces, found, formatter=str)
            self.stat_size.setText(fmt_bytes(report.total_bytes))
            self.stat_last.setText(report.scanned_at)
            # Actualizar Privacy Score
            try:
                from ..core.privacy_score import calculate_score, score_label, score_color
                score = calculate_score(report)
                self.score_value.setText(str(score))
                self.score_value.setStyleSheet(f"font-size: 48px; font-weight: 700; color: {score_color(score)};")
                self.score_label.setText(score_label(score))
                # Guardar en historial
                from ..core.privacy_score import record_score
                record_score(score, report)
                # Actualizar racha
                from ..core.streak import update_streak, get_streak_emoji, get_streak_message
                update_streak(found)
                streak = update_streak(found)
                self.streak_emoji.setText(get_streak_emoji())
                self.streak_value.setText(f"{streak.get('current', 0)} dias")
                self.streak_msg.setText(get_streak_message())
            except Exception:
                pass
        freed = getattr(self.mw, "session_freed_bytes", 0)
        count_to(self.stat_freed, freed, formatter=fmt_bytes)

    def _quick_clean(self):
        from ..core.quick_clean import run_quick_clean
        from ..core.notifications import notify_clean_complete
        from PySide6.QtWidgets import QMessageBox

        confirm = QMessageBox.question(
            self, "duAI",
            "Limpieza rapida: escanea y limpia todos los rastros en modo papelera.\n\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.mw.cli_output("Iniciando limpieza rapida...")
        from ..ui.worker import Worker

        def job():
            return run_quick_clean()

        def done(result):
            self.mw.session_freed_bytes += result["freed_bytes"]
            self.mw.last_report = result["report"]
            self.refresh_stats()
            self.mw.cli_output(f"Limpieza rapida completada: {result['cleaned']} items, {result['freed_bytes'] // 1024} KB liberados")
            notify_clean_complete(result["cleaned"], result["freed_bytes"])

        worker = Worker(job)
        worker.done.connect(done)
        worker.failed.connect(lambda m: self.mw.cli_output(f"Error: {m}"))
        worker.setParent(self.mw)
        worker.start()

    def _go_scan(self):
        self.mw.navigate(1)
        self.mw.scan_view.start_scan()
