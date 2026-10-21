"""Updater view with multi-step verification, rollback UI, update history, and scheduling."""

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget, QFrame, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QProgressBar, QListWidget, QListWidgetItem,
    QFileDialog, QApplication
)
from PySide6.QtGui import QDesktopServices

from ..core.updater import (
    CURRENT_VERSION,
    check_for_updates,
    check_for_updates_async,
    download_update,
    fetch_expected_sha256,
    should_check_on_startup,
    set_check_on_startup,
    get_update_history,
    add_update_history,
    clear_update_history,
    verify_signature,
    RollbackManager,
)
from ..i18n import t
from ..utils.logger import log, base_dir
from .worker import Worker
import os
import json
from datetime import datetime


class VerificationStepWidget(QFrame):
    """Visual step in the verification pipeline."""
    def __init__(self, step_id: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.setObjectName("verificationStep")
        self.setFixedHeight(60)
        self._status = "pending"  # pending, running, success, failed, skipped
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        # Status indicator
        self.indicator = QLabel()
        self.indicator.setFixedSize(24, 24)
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.indicator)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("stepTitle")
        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("stepDesc")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.desc_label)
        layout.addLayout(text_layout, 1)
        
        # Progress bar for running steps
        self.progress = QProgressBar()
        self.progress.setFixedWidth(120)
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.set_status("pending")
    
    def set_status(self, status: str):
        self._status = status
        icons = {
            "pending": "⏳",
            "running": "⟳",
            "success": "✓",
            "failed": "✗",
            "skipped": "⊘",
        }
        colors = {
            "pending": "#6B7280",
            "running": "#3B82F6",
            "success": "#10B981",
            "failed": "#EF4444",
            "skipped": "#9CA3AF",
        }
        self.indicator.setText(icons.get(status, "⏳"))
        self.indicator.setStyleSheet(f"font-size: 16px; color: {colors.get(status, '#6B7280')};")
        self.title_label.setStyleSheet(f"font-weight: 600; color: {colors.get(status, '#FFFFFF')};")
        self.progress.setVisible(status == "running")


class UpdateHistoryDialog(QDialog):
    """Dialog showing update history with rollback options."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("updater.history_title"))
        self.resize(600, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(t("updater.history_title"))
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #FFFFFF;")
        layout.addWidget(title)
        
        # List
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        layout.addWidget(self.list, 1)
        
        # Buttons
        btn_row = QHBoxLayout()
        self.rollback_btn = QPushButton(t("updater.rollback"))
        self.rollback_btn.setEnabled(False)
        self.rollback_btn.clicked.connect(self._do_rollback)
        clear_btn = QPushButton(t("updater.clear_history"))
        clear_btn.clicked.connect(self._clear_history)
        close_btn = QPushButton(t("common.close"))
        close_btn.clicked.connect(self.accept)
        
        btn_row.addWidget(self.rollback_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self._load_history()
    
    def _load_history(self):
        history = get_update_history()
        for entry in reversed(history):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry)
            
            date_str = entry.get("date", "")
            version = entry.get("version", "?")
            status = entry.get("status", "unknown")
            path = entry.get("path", "")
            
            status_icon = {"success": "✓", "failed": "✗", "rolled_back": "↩"}.get(status, "?")
            status_color = {"success": "#10B981", "failed": "#EF4444", "rolled_back": "#F59E0B"}.get(status, "#6B7280")
            
            item.setText(f"{status_icon}  v{version}  —  {date_str}  —  {path}")
            item.setForeground(Qt.GlobalColor.white)
            self.list.addItem(item)
    
    def _update_buttons(self):
        item = self.list.currentItem()
        if item:
            entry = item.data(Qt.ItemDataRole.UserRole)
            self.rollback_btn.setEnabled(entry.get("status") == "success" and entry.get("backup_path"))
        else:
            self.rollback_btn.setEnabled(False)
    
    def _do_rollback(self):
        item = self.list.currentItem()
        if not item:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, t("updater.rollback_confirm_title"),
            t("updater.rollback_confirm", version=entry.get("version", "?")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            rollback = RollbackManager()
            rollback.rollback_to(entry.get("backup_path", ""))
            QMessageBox.information(self, t("common.success"), t("updater.rollback_done"))
            self._load_history()
        except Exception as e:
            QMessageBox.critical(self, t("common.error"), str(e))
    
    def _clear_history(self):
        reply = QMessageBox.question(
            self, t("updater.clear_confirm_title"),
            t("updater.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_update_history()
            self._load_history()


class AutoUpdateDialog(QDialog):
    """Dialog for configuring auto-update schedule and skip version."""
    def __init__(self, parent=None, current_skip_version=""):
        super().__init__(parent)
        self.setWindowTitle(t("updater.auto_update_title"))
        self.resize(400, 300)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Schedule
        schedule_group = QFrame()
        schedule_group.setObjectName("settingsCard")
        schedule_layout = QVBoxLayout(schedule_group)
        
        schedule_title = QLabel(t("updater.schedule_title"))
        schedule_title.setObjectName("microLabel")
        schedule_layout.addWidget(schedule_title)
        
        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems([
            t("updater.schedule.never"),
            t("updater.schedule.daily"),
            t("updater.schedule.weekly"),
            t("updater.schedule.monthly"),
        ])
        schedule_layout.addWidget(self.schedule_combo)
        
        layout.addWidget(schedule_group)
        
        # Skip version
        skip_group = QFrame()
        skip_group.setObjectName("settingsCard")
        skip_layout = QVBoxLayout(skip_group)
        
        skip_title = QLabel(t("updater.skip_version"))
        skip_title.setObjectName("microLabel")
        skip_layout.addWidget(skip_title)
        
        self.skip_input = QLineEdit()
        self.skip_input.setPlaceholderText(t("updater.skip_version_placeholder"))
        self.skip_input.setText(current_skip_version)
        skip_layout.addWidget(self.skip_input)
        
        layout.addWidget(skip_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            "schedule": self.schedule_combo.currentText(),
            "skip_version": self.skip_input.text().strip(),
        }


class UpdaterView(QWidget):
    """Pantalla para comprobar y descargar actualizaciones de duAI con verificacion de integridad."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        self._download_worker = None
        self._download_url = ""
        self._signature_url = ""
        self._expected_sha256 = ""
        self._verification_steps = []
        self._rollback_manager = RollbackManager()
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)

        micro = QLabel(t("updater.title"))
        micro.setObjectName("microLabel")
        outer.addWidget(micro)

        title = QLabel(f"duAI v{CURRENT_VERSION}")
        title.setStyleSheet("font-size: 24px; font-weight: 300; letter-spacing: 2px; color: #FFFFFF;")
        outer.addWidget(title)

        self.status = QLabel(t("updater.up_to_date", version=CURRENT_VERSION))
        self.status.setObjectName("heroBody")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        btn_row = QHBoxLayout()
        self.check_btn = QPushButton(t("updater.check"))
        self.check_btn.clicked.connect(self._check)
        self.check_btn.setAccessibleName(t("updater.check"))
        self.check_btn.setAccessibleDescription(t("updater.check_desc"))
        
        self.download_btn = QPushButton(t("updater.download"))
        self.download_btn.setObjectName("shareBtn")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download)
        self.download_btn.setAccessibleName(t("updater.download"))
        self.download_btn.setAccessibleDescription(t("updater.download_desc"))
        
        self.history_btn = QPushButton(t("updater.history"))
        self.history_btn.clicked.connect(self._show_history)
        self.history_btn.setAccessibleName(t("updater.history"))
        
        self.auto_btn = QPushButton(t("updater.auto_settings"))
        self.auto_btn.clicked.connect(self._show_auto_settings)
        self.auto_btn.setAccessibleName(t("updater.auto_settings"))
        
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.history_btn)
        btn_row.addWidget(self.auto_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        # Verification pipeline
        pipeline_frame = QFrame()
        pipeline_frame.setObjectName("pipelineFrame")
        pipeline_layout = QVBoxLayout(pipeline_frame)
        pipeline_layout.setContentsMargins(16, 16, 16, 16)
        pipeline_layout.setSpacing(8)
        
        pipeline_title = QLabel(t("updater.verification_pipeline"))
        pipeline_title.setObjectName("microLabel")
        pipeline_layout.addWidget(pipeline_title)
        
        self.steps_container = QVBoxLayout()
        self.steps_container.setSpacing(4)
        pipeline_layout.addLayout(self.steps_container)
        
        outer.addWidget(pipeline_frame)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("hintLabel")
        outer.addWidget(self.progress_label)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(120)
        self.notes.setMaximumHeight(200)
        self.notes.setPlaceholderText(t("updater.release_notes"))
        outer.addWidget(self.notes)

        # Startup check option
        self.startup_check = QCheckBox(t("updater.check_on_startup"))
        self.startup_check.setChecked(should_check_on_startup())
        self.startup_check.toggled.connect(self._toggle_startup_check)
        outer.addWidget(self.startup_check)

        outer.addStretch(1)

        # Keyboard shortcuts
        self._setup_shortcuts()
        
        # Comprobar al abrir esta pestaña
        self._check()

    def _setup_shortcuts(self):
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("F5"), self, activated=self._check)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._check)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self._show_history)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._show_auto_settings)
        
        self.check_btn.setToolTip(f"{t('updater.check')} (F5)")
        self.download_btn.setToolTip(f"{t('updater.download')}")
        self.history_btn.setToolTip(f"{t('updater.history')} (Ctrl+H)")
        self.auto_btn.setToolTip(f"{t('updater.auto_settings')} (Ctrl+,)")

    def _create_verification_steps(self):
        """Create the verification pipeline steps."""
        # Clear existing
        while self.steps_container.count():
            child = self.steps_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self._verification_steps = [
            VerificationStepWidget("download", t("updater.step.download"), t("updater.step.download_desc")),
            VerificationStepWidget("sha256", t("updater.step.sha256"), t("updater.step.sha256_desc")),
            VerificationStepWidget("signature", t("updater.step.signature"), t("updater.step.signature_desc")),
            VerificationStepWidget("installer", t("updater.step.installer"), t("updater.step.installer_desc")),
        ]
        
        for step in self._verification_steps:
            self.steps_container.addWidget(step)

    def _reset_verification_steps(self):
        for step in self._verification_steps:
            step.set_status("pending")

    def _run_verification_pipeline(self, download_path: str):
        """Run the multi-step verification pipeline with visual feedback."""
        self._create_verification_steps()
        
        def run_step(step_index: int):
            if step_index >= len(self._verification_steps):
                self._on_verification_complete(True)
                return
            
            step = self._verification_steps[step_index]
            step.set_status("running")
            
            def do_verify():
                if step.step_id == "download":
                    return True, "Download complete"
                elif step.step_id == "sha256":
                    if not self._expected_sha256:
                        return "skipped", "No SHA-256 provided"
                    from ..core.updater import compute_sha256
                    actual = compute_sha256(download_path)
                    if actual.lower() == self._expected_sha256.lower():
                        return True, "SHA-256 matches"
                    return False, f"SHA-256 mismatch: expected {self._expected_sha256[:16]}..., got {actual[:16]}..."
                elif step.step_id == "signature":
                    # Verify Ed25519 signature if available
                    sig_path = download_path + ".sig"
                    if os.path.exists(sig_path):
                        if verify_signature(download_path, sig_path):
                            return True, "Ed25519 signature valid"
                        return False, "Invalid signature"
                    return "skipped", "No signature file"
                elif step.step_id == "installer":
                    # Verify installer integrity
                    if download_path.endswith(".exe"):
                        # Basic PE validation
                        with open(download_path, "rb") as f:
                            header = f.read(2)
                            if header == b"MZ":
                                return True, "Valid PE executable"
                            return False, "Invalid executable format"
                    return "skipped", "Not an installer"
                return True, "OK"
            
            # Run in thread
            from ..ui.worker import Worker
            worker = Worker(do_verify)
            
            def on_done(result):
                success, msg = result if isinstance(result, tuple) else (result, "")
                if success == "skipped":
                    step.set_status("skipped")
                elif success:
                    step.set_status("success")
                else:
                    step.set_status("failed")
                    self._on_verification_complete(False, msg)
                    return
                
                run_step(step_index + 1)
            
            def on_failed(msg):
                step.set_status("failed")
                self._on_verification_complete(False, msg)
            
            worker.done.connect(on_done)
            worker.failed.connect(on_failed)
            worker.start()
        
        run_step(0)

    def _on_verification_complete(self, success: bool, error_msg: str = ""):
        if success:
            self.status.setText(t("updater.verification_passed"))
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("updater.install"))
            self.download_btn.clicked.disconnect()
            self.download_btn.clicked.connect(lambda: self._install_update())
        else:
            self.status.setText(t("updater.verification_failed", error=error_msg))
            QMessageBox.critical(self, t("updater.verification_failed_title"), error_msg)

    def _check(self):
        if self._worker and self._worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.check_btn.setText(t("updater.checking"))
        self.status.setText("")
        self.progress_label.setText("")
        self.verified_label.setText("") if hasattr(self, 'verified_label') else None

        def job():
            return check_for_updates()

        def done(result):
            self.check_btn.setEnabled(True)
            self.check_btn.setText(t("updater.check"))
            if result.error:
                self.status.setText(t("updater.error", error=result.error))
                self.download_btn.setEnabled(False)
                return
            if result.available:
                self.status.setText(t("updater.available", version=result.latest_version))
                try:
                    from ..core.notifications import notify_update_available
                    notify_update_available(result.latest_version)
                except Exception:
                    pass
                self.notes.setPlainText(result.release_notes or "(sin notas de version)")
                self._download_url = result.download_url
                self._signature_url = result.signature_url
                self.download_btn.setEnabled(bool(result.download_url))

                if result.sha256_url:
                    expected = fetch_expected_sha256(result.sha256_url)
                    if expected:
                        self._expected_sha256 = expected
                    else:
                        self._expected_sha256 = ""
                elif result.expected_sha256:
                    self._expected_sha256 = result.expected_sha256
                else:
                    self._expected_sha256 = ""
            else:
                self.status.setText(t("updater.up_to_date", version=CURRENT_VERSION))
                self.notes.clear()
                self.download_btn.setEnabled(False)

        def failed(msg):
            self.check_btn.setEnabled(True)
            self.check_btn.setText(t("updater.check"))
            self.status.setText(t("updater.error", error=msg))

        self._worker = Worker(job)
        self._worker.done.connect(done)
        self._worker.failed.connect(failed)
        self._worker.start()

    def _download(self):
        if not self._download_url:
            return

        dest_dir = os.path.join(base_dir(), "updates")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, "duAI_update.exe")

        self.download_btn.setEnabled(False)
        self.download_btn.setText(t("updater.downloading"))

        def wrapped_job():
            return download_update(
                self._download_url,
                dest_path,
                expected_sha256=self._expected_sha256,
                signature_url=getattr(self, "_signature_url", ""),
            )

        def done(ok):
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("updater.download"))
            if ok:
                self.progress_label.setText(t("updater.download_done", path=dest_path))
                # Run verification pipeline
                self._run_verification_pipeline(dest_path)
            else:
                if self._expected_sha256:
                    self.status.setText(t("updater.sha256_mismatch"))
                else:
                    self.status.setText(t("updater.download_error"))

        def failed(msg):
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("updater.download"))
            self.status.setText(f"Error: {msg}")

        self._download_worker = Worker(wrapped_job)
        self._download_worker.done.connect(done)
        self._download_worker.failed.connect(failed)
        self._download_worker.start()

    def _install_update(self):
        """Install the verified update with rollback support."""
        dest_dir = os.path.join(base_dir(), "updates")
        dest_path = os.path.join(dest_dir, "duAI_update.exe")
        
        if not os.path.exists(dest_path):
            QMessageBox.warning(self, t("common.warning"), t("updater.file_missing"))
            return
        
        reply = QMessageBox.question(
            self, t("updater.install_title"),
            t("updater.install_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Create rollback point
        backup_path = self._rollback_manager.create_backup()
        
        try:
            # Launch installer
            import subprocess
            subprocess.Popen([dest_path, "/SILENT", "/NORESTART"], shell=False)
            
            # Record in history
            add_update_history({
                "version": "new",
                "date": datetime.now().isoformat(),
                "status": "success",
                "path": dest_path,
                "backup_path": backup_path,
            })
            
            QMessageBox.information(
                self, t("common.success"),
                t("updater.install_launched")
            )
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, t("common.error"), str(e))

    def _show_history(self):
        dialog = UpdateHistoryDialog(self)
        dialog.exec()

    def _show_auto_settings(self):
        from ..utils.settings import get_settings
        settings = get_settings()
        current_skip = settings.get("updater.skip_version", "")
        dialog = AutoUpdateDialog(self, current_skip)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            settings.set("updater.skip_version", values["skip_version"])
            settings.set("updater.schedule", values["schedule"])
            settings.save()

    def _toggle_startup_check(self, state):
        set_check_on_startup(bool(state))

    def _download_failed(self, message):
        self.download_btn.setEnabled(True)
        self.download_btn.setText(t("updater.download"))
        self.status.setText(f"Error: {message}")