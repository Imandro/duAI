"""UI interaction test: tema, idioma, tour, settings, vistas."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DUAI_NO_OPEN", "1")
os.environ.setdefault("DUAI_NO_DIALOGS", "1")
sys.argv = ["duai"]

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def step(name, fn):
    print(f"--- {name} ...", flush=True)
    try:
        out = fn()
        print(f"    OK: {out}", flush=True)
        return out
    except Exception:
        import traceback
        print("    FAIL:", flush=True)
        traceback.print_exc()
        return None


from duai.app import create_app

app, win = create_app()
win.show()

step("nav_all", lambda: [win.navigate(i) for i in range(win.stack.count())] and "ok")

step("apply_theme", win.apply_theme)
step("refresh_ui_text", win.refresh_ui_text)
step("refresh_settings", win.refresh_settings_page)

# Cambiar idioma a EN y volver a ES
def switch_lang():
    from duai.i18n import set_language, t, get_language
    set_language("en")
    en = t("analytics.title")
    set_language("es")
    es = t("analytics.title")
    win.refresh_ui_text()
    return {"en": en, "es": es, "lang": get_language()}
step("language_switch", switch_lang)

# Settings tabs
def settings_tabs():
    sw = win.settings_view
    tabs = sw.findChild(type(sw), None)
    from PySide6.QtWidgets import QTabWidget
    tw = sw.findChild(QTabWidget)
    names = []
    if tw:
        for i in range(tw.count()):
            tw.setCurrentIndex(i)
            names.append(tw.tabText(i))
        tw.setCurrentIndex(0)
    return names
step("settings_tabs", settings_tabs)

# Refresh de cada vista
def refresh_views():
    out = {}
    for attr in ("dashboard_view", "scan_view", "clean_view", "viral_view",
                 "updater_view", "analytics_view", "settings_view"):
        v = getattr(win, attr, None)
        if v is None:
            continue
        if hasattr(v, "refresh"):
            v.refresh()
            out[attr] = "refresh()"
        else:
            out[attr] = "no refresh"
    return out
step("view_refresh", refresh_views)

# Tour guiado
def demo_tour():
    win.start_demo_tour()
    dv = win.demo_view
    state = {"active": getattr(win, "demo_active", None)}
    if hasattr(dv, "_next_step"):
        dv._next_step()
        dv._next_step()
        state["after_next"] = "ok"
        state["tooltip_visible"] = dv.tooltip.isVisible()
        state["overlay_rect"] = str(dv.overlay.target_rect)
    dv._finish_demo(completed=False)
    state["ended"] = getattr(win, "demo_active", None)
    win.navigate(0)
    return state
step("demo_tour", demo_tour)

# Analytics rango
def analytics_range():
    av = win.analytics_view
    combo = None
    from PySide6.QtWidgets import QComboBox
    combos = av.findChildren(QComboBox)
    if combos:
        combo = combos[0]
        vals = [combo.itemText(i) for i in range(combo.count())]
        for i in range(combo.count()):
            combo.setCurrentIndex(i)
            av.refresh()
        combo.setCurrentIndex(0)
        return vals
    return "no combo"
step("analytics_range", analytics_range)

# Vista scan: modelo poblado tras escaneo simulado (sin escanear nada)
def scan_model():
    sv = win.scan_view
    return {"has_model": hasattr(sv, "table") or hasattr(sv, "model")}
step("scan_model", scan_model)

# Botones principales presentes
def main_buttons():
    d = win.dashboard_view
    return [b.objectName() or b.text() for b in d.findChildren(type(d))]
step("dashboard_children", main_buttons)

print("\nALL UI TESTS DONE", flush=True)
