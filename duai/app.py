import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from .core.scheduler import HotkeyWorker
from .core.session import has_running_session, stop_session
from .security import auth
from .ui.animations import (
    FadeStack,
    animate_max_height,
    fade_window,
    theme_dip,
)
from .ui.clean_view import CleanView
from .ui.console_view import CliBar
from .ui.dashboard import DashboardView
from .ui.panic_float import PanicFloatWidget
from .ui.panic_widget import PanicWidget
from .ui.scan_view import ScanView
from .ui.settings_view import SettingsView
from .ui.session_view import SessionView
from .ui.terminal_view import TerminalView
from .utils.settings import get_settings


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("duAI")
        self.setWindowIcon(QIcon(_icon_path()))
        self.setFixedSize(360, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 24)
        layout.setSpacing(14)
        micro = QLabel("ACCESO RESTRINGIDO")
        micro.setObjectName("microLabel")
        layout.addWidget(micro)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setPlaceholderText("Contrasena")
        self.input.returnPressed.connect(self._verify)
        layout.addWidget(self.input)
        btn = QPushButton("ENTRAR")
        btn.clicked.connect(self._verify)
        layout.addWidget(btn)
        self.error = QLabel("")
        self.error.setObjectName("statusLabel")
        layout.addWidget(self.error)

    def _verify(self):
        if auth.verify_password(self.input.text()):
            self.accept()
        else:
            self.error.setText("CONTRASENA INCORRECTA")
            self.input.selectAll()


class MainWindow(QMainWindow):
    NAV = ["RESUMEN", "ESCANEO", "LIMPIEZA", "SESION", "PANICO", "AJUSTES", "TERMINAL"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("duAI")
        self.resize(1060, 720)
        self.last_report = None
        self.session_freed_bytes = 0
        self._hotkey_worker = None
        self._float_widget = None
        self._boot_faded = False
        self.setWindowOpacity(0.0)

        from .core.cli_session import cleanup_orphan_sandboxes
        cleanup_orphan_sandboxes()

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 40, 0, 24)
        side_layout.setSpacing(2)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(4)
        brand_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._logo_label = QLabel()
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_logo()
        brand_box.addWidget(self._logo_label)
        side_layout.addLayout(brand_box)
        side_layout.addSpacing(24)
        self.nav_group = None
        self.nav_buttons = []
        from PySide6.QtWidgets import QButtonGroup

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, label in enumerate(self.NAV):
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self.navigate(i))
            self.nav_group.addButton(btn, index)
            self.nav_buttons.append(btn)
            side_layout.addWidget(btn)
        side_layout.addSpacing(12)

        self.theme_btn = QPushButton(self._theme_btn_label())
        self.theme_btn.setObjectName("navButton")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(lambda: self.apply_ui_mode(
            "oscuro" if get_settings().get("ui_mode") != "oscuro" else "claro"
        ))
        side_layout.addWidget(self.theme_btn)
        side_layout.addStretch(1)

        github_html = '<span style="color:#888;font-size:10px;">&#xf09b; Imandro</span>'
        github_link = QLabel(github_html)
        github_link.setObjectName("githubLink")
        github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(github_link)

        body_layout.addWidget(sidebar)

        self.stack = FadeStack()
        body_layout.addWidget(self.stack, 1)

        self.dashboard_view = DashboardView(self)
        self.scan_view = ScanView(self)
        self.clean_view = CleanView(self)
        self.session_view = SessionView(self)
        self.panic_widget = PanicWidget(self)
        self.settings_view = SettingsView(self)
        self.terminal_view = TerminalView(self)
        for view in (
            self.dashboard_view,
            self.scan_view,
            self.clean_view,
            self.session_view,
            self.panic_widget,
            self.settings_view,
            self.terminal_view,
        ):
            self.stack.addWidget(view)

        outer.addWidget(body, 1)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        self.cli_drawer = QTextEdit()
        self.cli_drawer.setObjectName("cliOutput")
        self.cli_drawer.setReadOnly(True)
        self.cli_drawer.setVisible(False)
        self.cli_drawer.setMaximumHeight(170)
        drawer_row = QHBoxLayout()
        drawer_row.setContentsMargins(0, 0, 0, 0)
        drawer_row.setSpacing(0)
        drawer_container = QWidget()
        drawer_container.setObjectName("cliBar")
        inner_drawer = QVBoxLayout(drawer_container)
        inner_drawer.setContentsMargins(0, 8, 0, 8)
        inner_drawer.setSpacing(4)
        drawer_header = QHBoxLayout()
        drawer_header.setContentsMargins(48, 0, 48, 0)
        cli_title = QLabel("SALIDA DE COMANDOS")
        cli_title.setObjectName("cliTitle")
        hide_btn = QPushButton("OCULTAR")
        hide_btn.setObjectName("cliHide")
        hide_btn.setFixedHeight(22)
        hide_btn.clicked.connect(self._hide_drawer)
        drawer_header.addWidget(cli_title)
        drawer_header.addStretch(1)
        drawer_header.addWidget(hide_btn)
        inner_drawer.addLayout(drawer_header)
        self.cli_drawer.setParent(None)
        inner_drawer.addWidget(self.cli_drawer)
        drawer_row.addWidget(drawer_container)
        self.drawer_container = drawer_container
        drawer_container.setVisible(False)
        outer.addWidget(drawer_container)

        self.cli_bar = CliBar(self)
        outer.addWidget(self.cli_bar)

        self.setCentralWidget(central)

        self.statusBar().setObjectName("statusBar")
        self.statusBar().setVisible(False)

        self.navigate(0)
        self._setup_tray()
        self.restart_hotkey()
        self.restart_auto_timer()
        if get_settings().get("float_visible"):
            self.show_panic_float(persist=False)

    def showEvent(self, event):
        if not self._boot_faded:
            self._boot_faded = True
            fade_window(self, duration=420, end=1.0)
        super().showEvent(event)

    # ---------------- navegacion ----------------

    def navigate(self, index):
        self.nav_buttons[index].setChecked(True)
        self.stack.setCurrentIndexAnimated(index)

    def _theme_btn_label(self):
        return "MODO OSCURO" if get_settings().get("ui_mode") != "oscuro" else "MODO CLARO"

    def _update_logo(self):
        from .ui.theme import current_mode
        mode = current_mode()
        if mode == "oscuro":
            name = "duAI_white.png"
        else:
            name = "duAI.png"
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(__file__), "..")
        path = os.path.join(base, "assets", name)
        if not os.path.exists(path):
            path = os.path.join(base, "assets", "duAI.png")
        if os.path.exists(path) and hasattr(self, "_logo_label"):
            pixmap = QPixmap(path)
            self._logo_label.setPixmap(pixmap.scaled(170, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def apply_ui_mode(self, mode):
        from PySide6.QtWidgets import QApplication

        from .ui.theme import apply_theme

        def _mid():
            get_settings().set("ui_mode", mode)
            apply_theme(QApplication.instance(), mode)
            self.theme_btn.setText(self._theme_btn_label())
            self.tray.setIcon(self._make_tray_icon())
            self._update_logo()
            if self._float_widget:
                self._float_widget.setStyleSheet("")

        theme_dip(self, duration=320, on_mid=_mid)
        self.cli_output(f"Tema aplicado: {mode}.")
        self.cli_drawer.verticalScrollBar().setValue(self.cli_drawer.verticalScrollBar().maximum())

    def refresh_settings_page(self):
        index = self.stack.indexOf(self.settings_view)
        old = self.settings_view
        self.settings_view = SettingsView(self)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(index, self.settings_view)

    def refresh_panic_page(self):
        index = self.stack.indexOf(self.panic_widget)
        old = self.panic_widget
        self.panic_widget = PanicWidget(self)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(index, self.panic_widget)

    # ---------------- cli ----------------

    def cli_output(self, line=""):
        if not self.drawer_container.isVisible():
            self.drawer_container.setVisible(True)
            self.drawer_container.setMaximumHeight(0)
            animate_max_height(self.drawer_container, 0, 170, 220)
        self.cli_drawer.append(line)

    def _hide_drawer(self):
        def _after_hide():
            self.drawer_container.setVisible(False)

        animate_max_height(self.drawer_container, self.drawer_container.height(), 0, 200, _after_hide)

    def cli_clear(self):
        self.cli_drawer.clear()

    def run_cli_worker(self, job, on_done, busy_note="PROCESANDO..."):
        from .ui.worker import Worker

        self._cli_workers = getattr(self, "_cli_workers", [])
        worker = Worker(job)
        worker.done.connect(on_done)
        worker.failed.connect(lambda message: self.cli_output(f"[ERROR] {message}"))
        worker.finished.connect(lambda: self._cli_workers.remove(worker) if worker in self._cli_workers else None)
        worker.setParent(self)
        worker.start()
        self._cli_workers.append(worker)

    # ---------------- bandeja / hotkey / timer ----------------

    def _make_tray_icon(self):
        icon = QIcon(_icon_path())
        if icon.isNull():
            from .ui.theme import color

            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(color("BG")))
            painter = QPainter(pixmap)
            painter.fillRect(1, 1, 14, 14, QColor(color("FG")))
            painter.fillRect(5, 5, 6, 6, QColor(color("BG")))
            painter.end()
            icon = QIcon(pixmap)
        return icon

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self._make_tray_icon(), self)
        menu = QMenu()
        open_action = QAction("ABRIR duAI", self)
        open_action.triggered.connect(self.showNormal)
        scan_action = QAction("ESCANEAR AHORA", self)
        scan_action.triggered.connect(self._tray_scan)
        panic_action = QAction("PANICO", self)
        panic_action.triggered.connect(self.trigger_panic)
        self._tray_float_action = QAction("BOTON FLOTANTE", self)
        self._tray_float_action.setCheckable(True)
        self._tray_float_action.setChecked(bool(get_settings().get("float_visible")))
        self._tray_float_action.triggered.connect(self._toggle_float_from_tray)
        quit_action = QAction("SALIR", self)
        quit_action.triggered.connect(self.close)
        for action in (open_action, scan_action, panic_action, self._tray_float_action):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("duAI — DON'T USE AI")
        self.tray.activated.connect(
            lambda reason: self.showNormal()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        self.tray.show()

    def _tray_scan(self):
        self.showNormal()
        self.cli_bar.run_text("escanear")

    def trigger_panic(self):
        self.showNormal()
        self.cli_bar.run_text("panico")

    # ---------------- boton flotante ----------------

    def show_panic_float(self, persist=True):
        if self._float_widget is None:
            self._float_widget = PanicFloatWidget(self)
        self._float_widget.show()
        self._float_widget.raise_()
        if persist:
            get_settings().set("float_visible", True)
            if hasattr(self, "_tray_float_action"):
                self._tray_float_action.setChecked(True)

    def hide_panic_float(self):
        if self._float_widget:
            self._float_widget.hide()
        get_settings().set("float_visible", False)
        if hasattr(self, "_tray_float_action"):
            self._tray_float_action.setChecked(False)

    def _toggle_float_from_tray(self, checked):
        if checked:
            self.show_panic_float()
        else:
            self.hide_panic_float()

    def restart_hotkey(self):
        if self._hotkey_worker:
            self._hotkey_worker.stop()
            self._hotkey_worker = None
        settings = get_settings()
        if settings.get("hotkey_enabled", True):
            self._hotkey_worker = HotkeyWorker(self.trigger_panic)
            self._hotkey_worker.start()

    def restart_auto_timer(self):
        settings = get_settings()
        minutes = int(settings.get("auto_interval_min") or 0)
        if not hasattr(self, "_auto_timer"):
            from PySide6.QtCore import QTimer

            self._auto_timer = QTimer(self)
            self._auto_timer.timeout.connect(self._auto_clean_tick)
        if minutes > 0:
            self._auto_timer.start(minutes * 60 * 1000)
        else:
            self._auto_timer.stop()

    def _auto_clean_tick(self):
        from .core.panic import perform_silent_clean
        from .ui.worker import Worker

        def job():
            return perform_silent_clean()

        def done(result):
            self.session_freed_bytes += result.freed_bytes
            self.dashboard_view.refresh_stats()
            self.tray.showMessage(
                "duAI", "Auto-limpieza completada.", QSystemTrayIcon.MessageIcon.NoIcon, 3000
            )

        worker = Worker(job)
        worker.done.connect(done)
        worker.failed.connect(lambda msg: None)
        worker.setParent(self)
        worker.start()

    def closeEvent(self, event):
        settings = get_settings()
        if self._float_widget:
            self._float_widget.hide()
        if has_running_session():
            stop_session()
        from .core.cli_session import stop_session as cli_stop, cleanup_orphan_sandboxes
        cli_stop()
        cleanup_orphan_sandboxes()
        if settings.get("auto_clean_on_exit"):
            from .core.panic import perform_silent_clean
            from .ui.worker import Worker

            def job():
                return perform_silent_clean()

            def done(result):
                self.session_freed_bytes += result.freed_bytes

            worker = Worker(job)
            worker.done.connect(done)
            worker.setParent(self)
            worker.start()
            worker.wait(2000)
        if settings.get("self_purge_on_exit"):
            from .core.selfclean import purge_logs, purge_own_recent_links

            purge_logs()
            purge_own_recent_links()
        if self._hotkey_worker:
            self._hotkey_worker.stop()
        event.accept()


def _icon_path():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    for name in ("duAI.ico", "duAI.png"):
        p = os.path.join(base, "assets", name)
        if os.path.exists(p):
            return p
    return ""


def _logo_path():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    for name in ("duAI.png", "duAI.ico"):
        p = os.path.join(base, "assets", name)
        if os.path.exists(p):
            return p
    return ""


def create_app(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("duAI")
    icon = QIcon(_icon_path())
    app.setWindowIcon(icon)
    from .ui.theme import apply_theme

    apply_theme(app, get_settings().get("ui_mode") or "claro")
    window = MainWindow()
    return app, window


def run_gui():
    app, window = create_app()
    if auth.has_password():
        dialog = LoginDialog()
        if not dialog.exec():
            return 0
    window.show()
    return app.exec()
