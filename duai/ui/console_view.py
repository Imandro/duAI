import os

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from ..core import reporter, session as session_core
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
        t for t in targets
        if t.id == filtro
        or (category and t.category == category)
        or filtro in t.name.lower()
        or filtro in t.category.lower()
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
            self.out(f"COMANDO DESCONOCIDO: {cmd}  ·  escribe AYUDA")
            return
        handler(args, flags)

    # ---------------- ayuda / estado ----------------

    def cmd_ayuda(self, args, flags):
        lines = [
            "ESCANEAR [filtro]      detecta rastros y abre la pestana ESCANEO (filtro: apps, navegador, sistema, id)",
            "LISTA [filtro]         objetivos del catalogo con sus ids",
            "ESTADO                 resumen actual de duAI",
            "LIMPIAR <sel>          sel: todo | apps | navegador | sistema | <id>...",
            "                       --modo=papelera|cuarentena|permanente   --confirmar (sin esto: vista previa)",
            "PANICO                 limpieza total silenciosa",
            "SESION <sitio>         chatgpt claude gemini perplexity copilot poe deepseek (perfil temporal)",
            "CERRARSESION           destruye la sesion protegida activa",
            "CERRARPESTAÑAS         cierra pestañas de IA en navegadores Chromium (--confirmar)",
            "TERMINAL [comando]     abre la terminal integrada o ejecuta un comando",
            "APPS                   lista apps de IA instaladas en el sistema",
            "DESINSTALAR <app>      --confirmar para ejecutar; sin ella solo muestra el comando",
            "EXPORTAR txt|csv       guarda el ultimo escaneo en el escritorio",
            "",
            "DESTINO <modo> · EXCLUIR <id> · PERMITIR <id> · EXCLUIDOS",
            "AUTOEXIT si|no · INTERVALO <min> · HOTKEY si|no · SIGILO si|no · TEMA claro|oscuro · WIDGET si|no",
            "CONTRASENA <clave> · SINCONTRASENA · HOSTS si|no · TAREA crear|quitar",
            "CUARENTENA ver|restaurar|vaciar · NAVEGADORES · PURGARLOGS · LIMPIARPANTALLA · SALIR",
        ]
        self.out("COMANDOS DISPONIBLES")
        for line in lines:
            self.out("  " + line)

    def cmd_estado(self, args, flags):
        settings = get_settings()
        report = getattr(self.mw, "last_report", None)
        if report:
            self.out(
                f"ULTIMO ESCANEO : {report.scanned_at} · {len(report.found_entries)} con rastros · "
                f"{fmt_bytes(report.total_bytes)}"
            )
        else:
            self.out("ULTIMO ESCANEO : ninguno todavia (usa ESCANEAR)")
        self.out(f"MODO DESTINO   : {_MODE_LABEL.get(settings.get('panic_mode'), 'papelera')}")
        self.out(
            f"AUTO-LIMPIEZA  : cerrar={'si' if settings.get('auto_clean_on_exit') else 'no'}"
            f" · intervalo={settings.get('auto_interval_min') or 0} min"
            f" · hotkey={'si' if settings.get('hotkey_enabled', True) else 'no'}"
            f" · sigilo={'si' if settings.get('self_purge_on_exit') else 'no'}"
        )
        exclusions = settings.get("exclusions") or []
        self.out(f"EXCLUIDOS      : {len(exclusions)}" + (f" ({', '.join(exclusions)})" if exclusions else ""))
        self.out(
            f"CUARENTENA     : {len(quarantined_items())} elementos · CONTRASENA: {'activa' if auth.has_password() else 'ninguna'}"
        )
        session_state = "ACTIVA · " + session_core.get_active_session().url if session_core.has_running_session() else "inactiva"
        self.out(f"SESION PROTEGIDA: {session_state}")
        self.out(f"LIBERADO ESTA SESION: {fmt_bytes(self.mw.session_freed_bytes)}")

    def cmd_lista(self, args, flags):
        filtro = args[0].lower() if args else ""
        exclusions = set(get_settings().get("exclusions") or [])
        shown = 0
        for entry in list_all_entries():
            label = entry["category"] + " " + entry["name"] + " " + entry["id"]
            if filtro and filtro not in label.lower():
                continue
            state = " [EXCLUIDO]" if entry["id"] in exclusions else ""
            self.out(f"  {entry['id']:<22} {entry['category']} · {entry['name']}{state}")
            shown += 1
        self.out(f"-- {shown} objetivos")

    def cmd_navegadores(self, args, flags):
        found = session_core.available_browsers()
        if not found:
            self.out("No se encontro Chrome, Edge ni Brave.")
            return
        for browser_id, path in found:
            self.out(f"  {browser_id:<8} {path}")

    def cmd_cerrarpestañas(self, args, flags):
        browsers = detect_cdp_browsers()
        if not browsers:
            self.out("No se detectaron navegadores Chromium corriendo.")
            return
        ai_info = find_ai_tabs(browsers)
        has_ai = any(info["ai_tabs"] for info in ai_info)
        if not has_ai:
            self.out("No hay pestañas de IA abiertas.")
            for info in ai_info:
                note = info.get("note", f'{len(info.get("ai_tabs", []))} pestañas IA')
                self.out(f"  {info['browser']}: {note}")
            return
        for info in ai_info:
            tabs = info.get("ai_tabs", [])
            note = info.get("note", "")
            if tabs:
                self.out(f"  {info['browser']}: {len(tabs)} pestañas de IA")
                for tab in tabs:
                    self.out(f"    - {tab['title'][:60]}  ({tab['url']})")
            elif note:
                self.out(f"  {info['browser']}: {note}")
        if "--confirmar" in flags or "confirmar" in flags:
            report = close_ai_tabs(browsers)
            self.out(f"Pestañas cerradas: {report['closed']}")
            for b in report["browsers"]:
                note = b.get("note", f'{b["closed"]} cerradas')
                self.out(f"  {b['browser']}: {note}")
        else:
            self.out("Anade --confirmar para cerrar las pestañas de IA.")

    # ---------------- acciones principales ----------------

    def cmd_escanear(self, args, flags):
        self.mw.navigate(1)
        started = self.mw.scan_view.start_scan()
        if started:
            self.out("Escaneo iniciado. Resultados en la pestana ESCANEO.")

    def cmd_limpiar(self, args, flags):
        tokens = [a for a in args if not a.startswith("-")]
        if not tokens:
            self.out("USO: limpiar todo|apps|navegador|sistema|<id>... [--modo=X] [--confirmar]")
            return
        selected, unknown = resolve_selection(tokens)
        if unknown:
            self.out("IDs desconocidos ignorados: " + ", ".join(unknown))
        if not selected:
            self.out("Nada que limpiar con esa seleccion.")
            return
        raw_mode = flags.get("modo") or get_settings().get("panic_mode") or "recycle"
        mode = _MODE_MAP.get(raw_mode, raw_mode)
        if mode not in ("recycle", "quarantine", "permanent"):
            mode = "recycle"
        confirm = bool(flags.get("confirmar"))
        self.mw.navigate(2)
        applied = self.mw.clean_view.apply_cli(selected, mode, confirm)
        if applied:
            verb = "LIMPIEZA REAL" if confirm else "VISTA PREVIA"
            self.out(f"{verb} lanzada sobre {len(selected)} objetivos (destino: {_MODE_LABEL[mode]}).")

    def cmd_panico(self, args, flags):
        self.mw.navigate(4)
        if self.mw.panic_widget.trigger_panic():
            self.out("MODO PANICO EN CURSO. Detalles en la pestana PANICO.")
        else:
            self.out("[ocupado] ya hay un panico en marcha.")

    def cmd_sesion(self, args, flags):
        if not args:
            self.out("USO: sesion chatgpt|claude|gemini|perplexity|copilot|poe|deepseek")
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
            self.out("No hay aplicaciones de IA registradas en el sistema.")
            return
        for index, app in enumerate(apps):
            quiet = "silenciable" if app["quiet_string"] else "asistido"
            self.out(f"  [{index}] {app['name']}  ({quiet})")
        self.out("-- usa DESINSTALAR <indice o nombre> [--confirmar]", )

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
            self.out("USO: desinstalar <indice o nombre> [--confirmar]")
            return
        token = args[0]
        app = self._resolve_app(token)
        if app is None:
            self.out("APP NO ENCONTRADA. usa APPS para listar.")
            return
        command = build_silent_command(app)
        if not command:
            self.out("Esta app no expone comando de desinstalacion util.")
            return
        if not flags.get("confirmar"):
            self.out("[SIMULACION] se ejecutaria:")
            self.out(f"  {command}")
            self.out("Anade --confirmar para desinstalar de verdad (y limpiar sus rastros despues).")
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
                self.out(f"[OK] {name} desinstalada ({detail}).")
                if cleaned is not None:
                    self.out(
                        f"     rastros posteriores: {cleaned.removed_items} elementos, "
                        f"{fmt_bytes(cleaned.freed_bytes)} liberados"
                    )
                self.mw.refresh_settings_page()
            else:
                self.out(f"[FALLO] {name}: {detail}")

        from .worker import Worker

        self.mw.run_cli_worker(job, done, "DESINSTALANDO...")

    # ---------------- configuracion ----------------

    def cmd_destino(self, args, flags):
        if not args:
            self.out("USO: destino papelera|cuarentena|permanente")
            return
        value = args[0].lower()
        if value not in MODES:
            self.out("DESTINO INVALIDO. opciones: papelera, cuarentena, permanente")
            return
        get_settings().set("panic_mode", _MODE_MAP[value])
        self.mw.refresh_panic_page()
        self.out(f"Modo de destino: {value}")

    def cmd_excluir(self, args, flags):
        if not args:
            self.out("USO: excluir <id>")
            return
        known = {e["id"] for e in list_all_entries()}
        exclusions = set(get_settings().get("exclusions") or [])
        added = []
        for target_id in args:
            if target_id in known:
                exclusions.add(target_id)
                added.append(target_id)
            else:
                self.out(f"ID desconocido: {target_id}")
        get_settings().set("exclusions", sorted(exclusions))
        if added:
            self.out("Excluidos (nunca se limpian): " + ", ".join(added))
            self.mw.refresh_settings_page()

    def cmd_permitir(self, args, flags):
        if not args:
            self.out("USO: permitir <id>")
            return
        exclusions = set(get_settings().get("exclusions") or [])
        removed = [t for t in args if t in exclusions]
        for t in removed:
            exclusions.discard(t)
        get_settings().set("exclusions", sorted(exclusions))
        self.out("Vuelven a ser limpiables: " + (", ".join(removed) or "nada"))
        if removed:
            self.mw.refresh_settings_page()

    def cmd_excluidos(self, args, flags):
        exclusions = get_settings().get("exclusions") or []
        self.out(", ".join(exclusions) if exclusions else "Sin exclusiones.")

    def cmd_autoexit(self, args, flags):
        if not args:
            self.out("USO: autoexit si|no")
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("auto_clean_on_exit", value)
        self.out(f"Limpieza automatica al cerrar: {'activada' if value else 'desactivada'}")
        self.mw.refresh_panic_page()

    def cmd_intervalo(self, args, flags):
        if not args:
            self.out("USO: intervalo <minutos 0-1440>")
            return
        try:
            minutes = max(0, min(1440, int(args[0])))
        except ValueError:
            self.out("MINUTOS INVALIDOS")
            return
        get_settings().set("auto_interval_min", minutes)
        self.mw.restart_auto_timer()
        self.out(
            f"Auto-limpieza periodica cada {minutes} minutos." if minutes else "Auto-limpieza periodica desactivada."
        )
        self.mw.refresh_panic_page()

    def cmd_hotkey(self, args, flags):
        if not args:
            self.out("USO: hotkey si|no")
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("hotkey_enabled", value)
        self.mw.restart_hotkey()
        self.out(f"Tecla global CTRL+ALT+D: {'activada' if value else 'desactivada'}")
        self.mw.refresh_panic_page()

    def cmd_sigilo(self, args, flags):
        if not args:
            self.out("USO: sigilo si|no")
            return
        value = args[0].lower() in ("si", "sí", "yes", "1", "true")
        get_settings().set("self_purge_on_exit", value)
        self.out(f"Modo sigilo: {'activado' if value else 'desactivado'}")
        self.mw.refresh_settings_page()

    def cmd_tema(self, args, flags):
        if not args or args[0].lower() not in ("claro", "oscuro"):
            self.out("USO: tema claro|oscuro")
            return
        self.mw.apply_ui_mode(args[0].lower())

    def cmd_widget(self, args, flags):
        if not args or args[0].lower() not in ("si", "no"):
            self.out("USO: widget si|no")
            return
        if args[0].lower() == "si":
            self.mw.show_panic_float()
            self.out("Boton flotante activado.")
        else:
            self.mw.hide_panic_float()
            self.out("Boton flotante desactivado.")

    def cmd_contrasena(self, args, flags):
        if not args:
            self.out("USO: contrasena <clave (min 4)>")
            return
        clave = args[0]
        if len(clave) < 4:
            self.out("Usa al menos 4 caracteres.")
            return
        auth.set_password(clave)
        self.out("Contrasena establecida. Se pedira al abrir duAI.")

    def cmd_sincontrasena(self, args, flags):
        auth.clear_password()
        self.out("Contrasena eliminada.")

    def cmd_hosts(self, args, flags):
        if not args:
            self.out("USO: hosts si|no")
            return
        enable = args[0].lower() in ("si", "sí", "yes", "1", "true")
        try:
            set_hosts_block(enable)
            self.out(f"Bloqueo de telemetria en hosts: {'activado' if enable else 'desactivado'}")
        except PermissionError:
            self.out("[ERROR] sin permisos de administrador para modificar el archivo hosts.")

    def cmd_tarea(self, args, flags):
        if not args:
            self.out("USO: tarea crear|quitar")
            return
        action = args[0].lower()
        if action == "crear":
            self.out("Tarea de inicio de sesion creada." if create_logon_task() else "No se pudo crear la tarea.")
        elif action == "quitar":
            self.out("Tarea eliminada." if remove_logon_task() else "No se pudo eliminar (puede que no exista).")
        else:
            self.out("ACCION INVALIDA. usa crear o quitar.")

    def cmd_cuarentena(self, args, flags):
        if not args:
            self.out("USO: cuarentena ver|restaurar|vaciar")
            return
        action = args[0].lower()
        if action == "ver":
            items = quarantined_items()
            if not items:
                self.out("Cuarentena vacia.")
                return
            for item in items:
                state = "" if item["available"] else " [PERDIDO]"
                self.out(f"  {item['token']}  {item['original']}{state}")
        elif action == "restaurar":
            restored = restore_all()
            self.out(f"{restored} elementos restaurados.")
            self.mw.refresh_settings_page()
        elif action == "vaciar":
            removed = purge_quarantine()
            self.out(f"Cuarentena vaciada ({removed} borrados definitivamente).")
            self.mw.refresh_settings_page()
        else:
            self.out("ACCION INVALIDA. usa ver, restaurar o vaciar.")

    def cmd_exportar(self, args, flags):
        report = getattr(self.mw, "last_report", None)
        if report is None:
            self.out("Aun no hay escaneo. Ejecuta ESCANEAR primero.")
            return
        fmt = args[0].lower() if args else "txt"
        desktop = expand("%USERPROFILE%/OneDrive/Desktop")
        try:
            if fmt == "csv":
                path = reporter.save_report_csv(report, os.path.join(desktop, "duai_reporte.csv"))
            elif fmt == "txt":
                path = reporter.save_report_txt(report, os.path.join(desktop, "duai_reporte.txt"))
            else:
                self.out("FORMATO INVALIDO. usa txt o csv.")
                return
            self.out(f"Reporte guardado: {path}")
        except OSError as exc:
            self.out(f"[ERROR] no se pudo guardar: {exc}")

    def cmd_purgarlogs(self, args, flags):
        purge_logs()
        removed = purge_own_recent_links()
        self.out(f"Bitacora vaciada ({logs_dir()}) y {removed} accesos recientes eliminados.")

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
        self.input.setPlaceholderText("comando...  (AYUDA para ver todos)")
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
