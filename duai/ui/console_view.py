import os

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from ..core import reporter, session as session_core
from ..i18n import t
from ..core.browser_tabs import close_ai_tabs, detect_cdp_browsers, find_ai_tabs
from ..core.cleaner import CleanOptions
from ..core.panic import perform_panic
from ..core.quarantine import purge_quarantine, quarantined_items, restore_all
from ..core.scheduler import create_logon_task, logon_task_exists, remove_logon_task
from ..core.selfclean import purge_logs, purge_own_recent_links
from ..core.system_clean import hosts_block_active, set_hosts_block
from ..core.targets import build_targets, list_all_entries
from ..core.uninstaller import (
    build_silent_command,
    clean_traces_for_app,
    find_installed_ai_apps,
    run_uninstall,
)
from ..security import auth
from ..utils.logger import logs_dir
from ..utils.paths import expand, fmt_bytes
from ..utils.settings import get_settings

ALIASES = {
    "help": "ayuda",
    "?": "ayuda",
    "status": "estado",
    "scan": "escanear",
    "clean": "limpiar",
    "panic": "panico",
    "clear": "limpiarpantalla",
    "cls": "limpiarpantalla",
    "exit": "salir",
    "quit": "salir",
}

CATEGORY_KEYS = {
    "apps": "Aplicaciones de IA",
    "aplicaciones": "Aplicaciones de IA",
    "navegador": "Navegador",
    "navegadores": "Navegador",
    "sistema": "Sistema",
    "registro": "Sistema",
}

MODES = ("papelera", "cuarentena", "permanente")
_MODE_MAP = {"papelera": "recycle", "cuarentena": "quarantine", "permanente": "permanent"}
_MODE_LABEL = {"recycle": "papelera", "quarantine": "cuarentena", "permanent": "permanente"}


def parse_command(text):
    parts = text.strip().split()
    if not parts:
        return None, [], {}
    cmd = parts[0].lower()
    cmd = ALIASES.get(cmd, cmd)
    args = []
    flags = {}
    for token in parts[1:]:
        if token.startswith("--"):
            body = token[2:]
            if "=" in body:
                key, value = body.split("=", 1)
                flags[key.lower()] = value.lower()
            else:
                flags[body.lower()] = True
        else:
            args.append(token)
    return cmd, args, flags


def targets_for_filter(filtro):
    exclusions = set(get_settings().get("exclusions") or [])
    targets = build_targets(exclusions=exclusions)
    if not filtro:
        return targets
    category = CATEGORY_KEYS.get(filtro)
    return [
        target for target in targets
        if target.id == filtro
        or (category and target.category == category)
        or filtro in target.name.lower()
        or filtro in target.category.lower()
    ]


def resolve_selection(tokens):
    exclusions = set(get_settings().get("exclusions") or [])
    all_targets = build_targets(exclusions=exclusions)
    if "todo" in tokens:
        return {t.id for t in all_targets}, []
    ids = []
    unknown = []
    for token in tokens:
        category = CATEGORY_KEYS.get(token)
        if category:
            ids.extend(t.id for t in all_targets if t.category == category)
        elif any(t.id == token for t in all_targets):
            ids.append(token)
        else:
            unknown.append(token)
    seen = set()
    unique = []
    for target_id in ids:
        if target_id not in seen:
            seen.add(target_id)
            unique.append(target_id)
    return set(unique), unknown


class CommandRouter:
    def __init__(self, main_window):
        self.mw = main_window
        self._last_apps = []

    @property
    def out(self):
        return self.mw.cli_output

    def execute(self, text):
        cmd, args, flags = parse_command(text)
        if cmd is None:
            return
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            self._run_powershell(text)
            return
        handler(args, flags)

    def _run_powershell(self, text):
        import subprocess

        self.out(f"PS> {text}")
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", text],
                capture_output=True, text=True, timeout=30,
            )
            if result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    self.out(line)
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines():
                    self.out(f"[ERROR] {line}")
            if result.returncode != 0:
                self.out(t("cli.code", code=result.returncode))
        except subprocess.TimeoutExpired:
            self.out(t("cli.timeout"))
        except Exception as exc:
            self.out(f"[ERROR] {exc}")

    # ---------------- ayuda / estado ----------------

    def cmd_ayuda(self, args, flags):
        lines = [
            t("cli.help_line.escanear"),
            t("cli.help_line.lista"),
            t("cli.help_line.estado"),
            t("cli.help_line.limpiar"),
            t("cli.help_line.limpiar_opts"),
            t("cli.help_line.panico"),
            t("cli.help_line.sesion"),
            t("cli.help_line.cerrarsesion"),
            t("cli.help_line.cerrarpestanas"),
            t("cli.help_line.terminal"),
            t("cli.help_line.apps"),
            t("cli.help_line.desinstalar"),
            t("cli.help_line.exportar"),
            "",
            t("cli.help_line.config1"),
            t("cli.help_line.config2"),
            t("cli.help_line.config3"),
            t("cli.help_line.config4"),
        ]
        self.out(t("cli.help_title"))
        for line in lines:
            self.out("  " + line)

    def cmd_estado(self, args, flags):
        settings = get_settings()
        report = getattr(self.mw, "last_report", None)
        if report:
            self.out(
                t("cli.last_scan", time=report.scanned_at, count=len(report.found_entries),
                  bytes=fmt_bytes(report.total_bytes))
            )
        else:
            self.out(t("cli.last_scan_none"))
        self.out(t("cli.dest_mode", mode=_MODE_LABEL.get(settings.get('panic_mode'), 'papelera')))
        self.out(
            t("cli.auto_status",
              val='si' if settings.get('auto_clean_on_exit') else 'no',
              min=settings.get('auto_interval_min') or 0,
              val2='si' if settings.get('hotkey_enabled', True) else 'no',
              val3='si' if settings.get('self_purge_on_exit') else 'no')
        )
        exclusions = settings.get("exclusions") or []
        self.out(t("cli.excluded", count=len(exclusions)) + (f" ({', '.join(exclusions)})" if exclusions else ""))
        self.out(
            t("cli.quarantine", count=len(quarantined_items()),
              pwd='activa' if auth.has_password() else 'ninguna')
        )
        session_state = t("cli.session_active") + " · " + session_core.get_active_session().url if session_core.has_running_session() else t("cli.session_inactive")
        self.out(t("cli.session_state", state=session_state))
        self.out(t("cli.freed", bytes=fmt_bytes(self.mw.session_freed_bytes)))

    def cmd_lista(self, args, flags):
        filtro = args[0].lower() if args else ""
        exclusions = set(get_settings().get("exclusions") or [])
        shown = 0
        for entry in list_all_entries():
            label = entry["category"] + " " + entry["name"] + " " + entry["id"]
            if filtro and filtro not in label.lower():
                continue
            state = f" [{t('cli.excluded_label')}]" if entry["id"] in exclusions else ""
            self.out(f"  {entry['id']:<22} {entry['category']} · {entry['name']}{state}")
            shown += 1
        self.out(f"-- {t('cli.targets_count', count=shown)}")

    def cmd_navegadores(self, args, flags):
        found = session_core.available_browsers()
        if not found:
            self.out(t("cli.no_chrome"))
            return
        for browser_id, path in found:
            self.out(f"  {browser_id:<8} {path}")

    def cmd_cerrarpestañas(self, args, flags):
        browsers = detect_cdp_browsers()
        if not browsers:
            self.out(t("cli.no_browsers"))
            return
        ai_info = find_ai_tabs(browsers)
        has_ai = any(info["ai_tabs"] for info in ai_info)
        if not has_ai:
            self.out(t("cli.no_ai_tabs"))
            for info in ai_info:
                note = info.get("note", t("cli.ai_tabs", count=len(info.get("ai_tabs", []))))
                self.out(f"  {info['browser']}: {note}")
            return
        for info in ai_info:
            tabs = info.get("ai_tabs", [])
            note = info.get("note", "")
            if tabs:
                self.out(f"  {info['browser']}: {t('cli.ai_tabs', count=len(tabs))}")
                for tab in tabs:
                    self.out(f"    - {tab['title'][:60]}  ({tab['url']})")
            elif note:
                self.out(f"  {info['browser']}: {note}")
        if "--confirmar" in flags or "confirmar" in flags:
            report = close_ai_tabs(browsers)
            self.out(t("cli.tabs_closed", count=report['closed']))
            for b in report["browsers"]:
                note = b.get("note", t("cli.tabs_closed", count=b["closed"]))
                self.out(f"  {b['browser']}: {note}")
        else:
            self.out(t("cli.tabs_confirm"))

    # ---------------- acciones principales ----------------

    def cmd_escanear(self, args, flags):
        self.mw.navigate(1)
        started = self.mw.scan_view.start_scan()
        if started:
            self.out(t("cli.scan_started"))

    def cmd_limpiar(self, args, flags):
        tokens = [a for a in args if not a.startswith("-")]
        if not tokens:
            self.out(t("cli.clean_usage"))
            return
        selected, unknown = resolve_selection(tokens)
        if unknown:
            self.out(t("cli.unknown_ids") + ", ".join(unknown))
        if not selected:
            self.out(t("cli.nothing_to_clean"))
            return
        raw_mode = flags.get("modo") or get_settings().get("panic_mode") or "recycle"
        mode = _MODE_MAP.get(raw_mode, raw_mode)
        if mode not in ("recycle", "quarantine", "permanent"):
            mode = "recycle"
        confirm = bool(flags.get("confirmar"))
        self.mw.navigate(2)
        applied = self.mw.clean_view.apply_cli(selected, mode, confirm)
        if applied:
            verb = t("cli.clean_real") if confirm else t("cli.clean_preview")
            self.out(t("cli.clean_launched", verb=verb, count=len(selected), mode=_MODE_LABEL[mode]))

    def cmd_panico(self, args, flags):
        self.mw.navigate(4)
        if self.mw.panic_widget.trigger_panic():
            self.out(t("cli.panic_running"))
        else:
            self.out(t("cli.panic_busy"))

    def cmd_sesion(self, args, flags):
        if not args:
            self.out(t("cli.session_usage"))
            return
        self.mw.navigate(3)
        ok, message = self.mw.session_view.open_site(args[0])
        self.out(message)

    def cmd_cerrarsesion(self, args, flags):
        self.mw.navigate(3)
        ok, message = self.mw.session_view.stop_action()
        self.out(message)

    def cmd_terminal(self, args, flags):
        self.mw.navigate(6)
        if args:
            self.mw.terminal_view.run_command(" ".join(args))

    # ---------------- desinstalacion avanzada ----------------

    def cmd_apps(self, args, flags):
        apps = find_installed_ai_apps()
        self._last_apps = apps
        if not apps:
            self.out(t("cli.no_apps"))
            return
        for index, app in enumerate(apps):
            quiet = t("cli.silent") if app["quiet_string"] else t("cli.assisted")
            self.out(f"  [{index}] {app['name']}  ({quiet})")
        self.out(t("cli.uninstall_hint"), )

    def _resolve_app(self, token):
        if not self._last_apps:
            self._last_apps = find_installed_ai_apps()
        apps = self._last_apps
        if token.isdigit():
            index = int(token)
            if 0 <= index < len(apps):
                return apps[index]
            return None
        lowered = token.lower()
        return next((a for a in apps if lowered in a["name"].lower()), None)

    def cmd_desinstalar(self, args, flags):
        if not args:
            self.out(t("cli.uninstall_usage"))
            return
        token = args[0]
        app = self._resolve_app(token)
        if app is None:
            self.out(t("cli.app_not_found"))
            return
        command = build_silent_command(app)
        if not command:
            self.out(t("cli.app_no_uninstall"))
            return
        if not flags.get("confirmar"):
            self.out(t("cli.simulation"))
            self.out(f"  {command}")
            self.out(t("cli.uninstall_confirm_hint"))
            return

        def job():
            from PySide6.QtCore import QObject

            ok, detail = run_uninstall(app)
            cleaned = None
            if ok:
                cleaned = clean_traces_for_app(app["name"])
            return app["name"], ok, detail, cleaned

        def done(payload):
            name, ok, detail, cleaned = payload
            if ok:
                self.out(t("cli.uninstalled", name=name, detail=detail))
                if cleaned is not None:
                    self.out(
                        t("cli.traces_after", count=cleaned.removed_items,
                          bytes=fmt_bytes(cleaned.freed_bytes))
                    )
                self.mw.refresh_settings_page()
            else:
                self.out(t("cli.uninstall_fail", name=name, detail=detail))

        from .worker import Worker

        self.mw.run_cli_worker(job, done, t("cli.uninstalling"))

    # ---------------- configuracion ----------------

    def cmd_destino(self, args, flags):
        if not args:
            self.out(t("cli.dest_usage"))
            return
        value = args[0].lower()
        if value not in MODES:
            self.out(t("cli.dest_invalid"))
            return
        get_settings().set("panic_mode", _MODE_MAP[value])
        self.mw.refresh_panic_page()
        self.out(t("cli.dest_set", value=value))

    def cmd_excluir(self, args, flags):
        if not args:
            self.out(t("cli.exclude_usage"))
            return
        known = {e["id"] for e in list_all_entries()}
        exclusions = set(get_settings().get("exclusions") or [])
        added = []
        for target_id in args:
            if target_id in known:
                exclusions.add(target_id)
                added.append(target_id)
            else:
                self.out(t("cli.exclude_unknown", id=target_id))
        get_settings().set("exclusions", sorted(exclusions))
        if added:
            self.out(t("cli.excluded_list") + ", ".join(added))
            self.mw.refresh_settings_page()

    def cmd_permitir(self, args, flags):
        if not args:
            self.out(t("cli.allow_usage"))
            return
        exclusions = set(get_settings().get("exclusions") or [])
        removed = [x for x in args if x in exclusions]
        for x in removed:
            exclusions.discard(x)
        get_settings().set("exclusions", sorted(exclusions))
        self.out(t("cli.allow_restored") + (", ".join(removed) or t("cli.no_items")))
        if removed:
            self.mw.refresh_settings_page()

    def cmd_excluidos(self, args, flags):
        exclusions = get_settings().get("exclusions") or []
        self.out(", ".join(exclusions) if exclusions else t("cli.no_exclusions"))

    def cmd_autoexit(self, args, flags):
        if not args:
            self.out(t("cli.autoexit_usage"))
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("auto_clean_on_exit", value)
        self.out(t("cli.autoexit_set", val='activada' if value else 'desactivada'))
        self.mw.refresh_panic_page()

    def cmd_intervalo(self, args, flags):
        if not args:
            self.out(t("cli.interval_usage"))
            return
        try:
            minutes = max(0, min(1440, int(args[0])))
        except ValueError:
            self.out(t("cli.interval_invalid"))
            return
        get_settings().set("auto_interval_min", minutes)
        self.mw.restart_auto_timer()
        self.out(
            t("cli.interval_set", minutes=minutes) if minutes else t("cli.interval_off")
        )
        self.mw.refresh_panic_page()

    def cmd_hotkey(self, args, flags):
        if not args:
            self.out(t("cli.hotkey_usage"))
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("hotkey_enabled", value)
        self.mw.restart_hotkey()
        self.out(t("cli.hotkey_set", val='activada' if value else 'desactivada'))
        self.mw.refresh_panic_page()

    def cmd_sigilo(self, args, flags):
        if not args:
            self.out(t("cli.stealth_usage"))
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("self_purge_on_exit", value)
        self.out(t("cli.stealth_set", val='activado' if value else 'desactivado'))
        self.mw.refresh_settings_page()

    def cmd_tema(self, args, flags):
        if not args or args[0].lower() not in ("claro", "oscuro"):
            self.out(t("cli.theme_usage"))
            return
        self.mw.apply_ui_mode(args[0].lower())

    def cmd_widget(self, args, flags):
        if not args or args[0].lower() not in ("si", "no"):
            self.out(t("cli.widget_usage"))
            return
        if args[0].lower() == "si":
            self.mw.show_panic_float()
            self.out(t("cli.widget_on"))
        else:
            self.mw.hide_panic_float()
            self.out(t("cli.widget_off"))

    def cmd_contrasena(self, args, flags):
        if not args:
            self.out(t("cli.pwd_usage"))
            return
        clave = args[0]
        if len(clave) < 4:
            self.out(t("cli.pwd_min"))
            return
        auth.set_password(clave)
        self.out(t("cli.pwd_set"))

    def cmd_sincontrasena(self, args, flags):
        auth.clear_password()
        self.out(t("cli.pwd_removed"))

    def cmd_hosts(self, args, flags):
        if not args:
            self.out(t("cli.hosts_usage"))
            return
        enable = args[0].lower() in ("si", "sí", "yes", "1", "true")
        try:
            set_hosts_block(enable)
            self.out(t("cli.hosts_set", val='activado' if enable else 'desactivado'))
        except PermissionError:
            self.out(t("cli.hosts_admin_error"))

    def cmd_tarea(self, args, flags):
        if not args:
            self.out(t("cli.task_usage"))
            return
        action = args[0].lower()
        if action == "crear":
            self.out(t("cli.task_created") if create_logon_task() else t("cli.task_create_fail"))
        elif action == "quitar":
            self.out(t("cli.task_deleted") if remove_logon_task() else t("cli.task_delete_fail"))
        else:
            self.out(t("cli.task_invalid"))

    def cmd_cuarentena(self, args, flags):
        if not args:
            self.out(t("cli.quarantine_usage"))
            return
        action = args[0].lower()
        if action == "ver":
            items = quarantined_items()
            if not items:
                self.out(t("cli.quarantine_empty"))
                return
            for item in items:
                state = "" if item["available"] else f" {t('cli.quarantine_lost')}"
                self.out(f"  {item['token']}  {item['original']}{state}")
        elif action == "restaurar":
            restored = restore_all()
            self.out(t("cli.quarantine_restored", count=restored))
            self.mw.refresh_settings_page()
        elif action == "vaciar":
            removed = purge_quarantine()
            self.out(t("cli.quarantine_emptied", count=removed))
            self.mw.refresh_settings_page()
        else:
            self.out(t("cli.quarantine_invalid"))

    def cmd_exportar(self, args, flags):
        report = getattr(self.mw, "last_report", None)
        if report is None:
            self.out(t("cli.no_scan"))
            return
        fmt = args[0].lower() if args else "txt"
        desktop = expand("%USERPROFILE%/OneDrive/Desktop")
        try:
            if fmt == "csv":
                path = reporter.save_report_csv(report, os.path.join(desktop, "duai_reporte.csv"))
            elif fmt == "txt":
                path = reporter.save_report_txt(report, os.path.join(desktop, "duai_reporte.txt"))
            else:
                self.out(t("cli.export_invalid"))
                return
            self.out(t("cli.export_saved", path=path))
        except OSError as exc:
            self.out(t("cli.export_error", exc=exc))

    def cmd_purgarlogs(self, args, flags):
        purge_logs()
        removed = purge_own_recent_links()
        self.out(t("cli.purge_done", dir=logs_dir(), count=removed))

    def cmd_limpiarpantalla(self, args, flags):
        self.mw.cli_clear()

    def cmd_salir(self, args, flags):
        self.mw.close()


class CliBar(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.setObjectName("cliBar")
        self.router = CommandRouter(main_window)
        self._history = []
        self._history_index = -1

        row = QHBoxLayout(self)
        row.setContentsMargins(48, 10, 48, 10)
        row.setSpacing(10)
        mark = QLabel(">")
        mark.setObjectName("promptMark")
        self.input = QLineEdit()
        self.input.setObjectName("cliInput")
        self.input.setPlaceholderText(t("cli.placeholder"))
        self.input.returnPressed.connect(self._submit)
        self.input.installEventFilter(self)
        row.addWidget(mark)
        row.addWidget(self.input, 1)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent

        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._history_back()
                return True
            if key == Qt.Key.Key_Down:
                self._history_forward()
                return True
        return super().eventFilter(obj, event)

    def _history_back(self):
        if not self._history:
            return
        if self._history_index < 0:
            self._history_index = len(self._history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self.input.setText(self._history[self._history_index])

    def _history_forward(self):
        if not self._history or self._history_index < 0:
            return
        self._history_index += 1
        if self._history_index >= len(self._history):
            self._history_index = -1
            self.input.setText("")
        else:
            self.input.setText(self._history[self._history_index])

    def run_text(self, text):
        self.input.setText(text)
        self._submit()

    def _submit(self):
        text = self.input.text().strip()
        if not text:
            return
        self._history.append(text)
        self._history_index = -1
        self.input.clear()
        self.mw.cli_output(f"> {text}")
        self.router.execute(text)
