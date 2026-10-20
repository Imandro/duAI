from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QCheckBox,
)

from ..core.updater import (
    CURRENT_VERSION,
    check_for_updates,
    check_for_updates_async,
    download_update,
    fetch_expected_sha256,
    should_check_on_startup,
    set_check_on_startup,
)
from ..i18n import t
from ..utils.logger import log, base_dir
from .worker import Worker
import os


class UpdaterView(QWidget):
    """Pantalla para comprobar y descargar actualizaciones de duAI con verificacion de integridad."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._worker = None
        self._download_worker = None
        self._download_url = ""
        self._expected_sha256 = ""

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
        self.download_btn = QPushButton(t("updater.download"))
        self.download_btn.setObjectName("shareBtn")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download)
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.download_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        self.progress = QLabel("")
        self.progress.setObjectName("hintLabel")
        outer.addWidget(self.progress)

        self.verified_label = QLabel("")
        self.verified_label.setObjectName("hintLabel")
        outer.addWidget(self.verified_label)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(120)
        self.notes.setMaximumHeight(200)
        self.notes.setPlaceholderText(t("updater.release_notes"))
        outer.addWidget(self.notes)

        # Opcion de comprobar al inicio
        self.startup_check = QCheckBox(t("updater.check_on_startup"))
        self.startup_check.setChecked(should_check_on_startup())
        self.startup_check.toggled.connect(self._toggle_startup_check)
        outer.addWidget(self.startup_check)

        outer.addStretch(1)

        # Comprobar al abrir esta pestaña
        self._check()

    def _check(self):
        if self._worker and self._worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.check_btn.setText("COMPROBANDO...")
        self.status.setText("")
        self.verified_label.setText("")

        def job():
            return check_for_updates()

        def done(result):
            self.check_btn.setEnabled(True)
            self.check_btn.setText(t("updater.check"))
            if result.error:
                self.status.setText(t("updater.error", error=result.error))
                self.download_btn.setEnabled(False)
                self.verified_label.setText("")
                return
            if result.available:
                self.status.setText(t("updater.available", version=result.latest_version))
                self.notes.setPlainText(result.release_notes or "(sin notas de version)")
                self._download_url = result.download_url
                self.download_btn.setEnabled(bool(result.download_url))

                # Obtener hash esperado (del .sha256 adjunto o de las release notes)
                if result.sha256_url:
                    expected = fetch_expected_sha256(result.sha256_url)
                    if expected:
                        self._expected_sha256 = expected
                        self.verified_label.setText("Hash SHA-256 disponible para verificacion.")
                    else:
                        self._expected_sha256 = ""
                        self.verified_label.setText("No se encontro hash SHA-256 para verificar.")
                elif result.expected_sha256:
                    self._expected_sha256 = result.expected_sha256
                    self.verified_label.setText("Hash SHA-256 extraido de las notas de version.")
                else:
                    self._expected_sha256 = ""
                    self.verified_label.setText("ADVERTENCIA: sin hash SHA-256, la descarga no se verificara.")
            else:
                self.status.setText(t("updater.up_to_date", version=CURRENT_VERSION))
                self.notes.clear()
                self.download_btn.setEnabled(False)
                self.verified_label.setText("")

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
        self.download_btn.setText("DESCARGANDO...")

        def wrapped_job():
            return download_update(
                self._download_url,
                dest_path,
                expected_sha256=self._expected_sha256,
            )

        def done(ok):
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("updater.download"))
            if ok:
                self.status.setText(t("updater.download_done", path=dest_path))
                if self._expected_sha256:
                    self.verified_label.setText("Descarga verificada correctamente (SHA-256 OK).")
                QMessageBox.information(
                    self, "duAI",
                    f"Actualizacion descargada en:\n{dest_path}\n\nEjecuta el instalador para actualizar."
                )
            else:
                if self._expected_sha256:
                    self.status.setText("Error: el hash SHA-256 no coincide. Descarga cancelada por seguridad.")
                else:
                    self.status.setText("Error al descargar la actualizacion.")

        self._download_worker = Worker(wrapped_job)
        self._download_worker.done.connect(done)
        self._download_worker.failed.connect(lambda m: self._download_failed(m))
        self._download_worker.start()

    def _download_failed(self, message):
        self.download_btn.setEnabled(True)
        self.download_btn.setText(t("updater.download"))
        self.status.setText(f"Error: {message}")

    def _toggle_startup_check(self, state):
        set_check_on_startup(bool(state))
