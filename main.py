import argparse
import os
import sys
import time


def main():
    parser = argparse.ArgumentParser(prog="duAI", description="duAI - Don't Use AI")
    parser.add_argument("--panic", action="store_true", help="Ejecuta limpieza total silenciosa y sale")
    parser.add_argument("--screenshots", action="store_true", help="Captura screenshots de cada tab y sale")
    parser.add_argument("--check-updates", action="store_true", help="Comprueba actualizaciones y sale")
    parser.add_argument("--portable", action="store_true", help="Modo portable (configuracion junto al ejecutable, ideal para USB)")
    args = parser.parse_args()

    # Activar modo portable ANTES de importar duai para que base_dir() redirija correctamente
    if args.portable:
        from duai.utils.logger import set_portable_mode

        set_portable_mode(True)

    if args.panic:
        from duai.core.panic import format_result_summary, perform_panic

        result = perform_panic()
        print(format_result_summary(result))
        return 0

    if args.screenshots:
        return _take_screenshots()

    if args.check_updates:
        from duai.core.updater import check_for_updates, CURRENT_VERSION

        result = check_for_updates()
        if result.error:
            print(f"Error: {result.error}")
            return 1
        if result.available:
            print(f"Nueva version disponible: {result.latest_version} (actual: {CURRENT_VERSION})")
            if result.download_url:
                print(f"Descarga: {result.download_url}")
        else:
            print(f"duAI esta actualizado (version {CURRENT_VERSION})")
        return 0

    from duai.app import run_gui

    sys.exit(run_gui())


def _take_screenshots():
    os.environ["QT_QPA_PLATFORM"] = "windows"
    from duai.app import create_app
    from duai.utils.settings import get_settings

    app, window = create_app()
    window.show()
    app.processEvents()
    time.sleep(0.5)

    # dark mode for screenshots
    get_settings().set("ui_mode", "oscuro")
    from duai.ui.theme import apply_theme
    apply_theme(app, "oscuro")
    window.show()
    app.processEvents()
    time.sleep(0.3)

    out_dir = os.path.join(os.path.dirname(__file__), "website", "assets", "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    tabs = ["dashboard", "scan", "clean", "panic", "session", "settings", "terminal"]

    for i, name in enumerate(tabs):
        window.navigate(i)
        app.processEvents()
        time.sleep(0.8)
        screen = app.primaryScreen()
        pixmap = screen.grabWindow(window.winId())
        path = os.path.join(out_dir, f"{name}.png")
        pixmap.save(path, "PNG")
        kb = os.path.getsize(path) / 1024
        print(f"  {name}.png ({kb:.0f} KB)")

    # light mode screenshots
    get_settings().set("ui_mode", "claro")
    apply_theme(app, "claro")
    window.show()
    app.processEvents()
    time.sleep(0.3)

    light_dir = os.path.join(out_dir, "light")
    os.makedirs(light_dir, exist_ok=True)

    for i, name in enumerate(tabs):
        window.navigate(i)
        app.processEvents()
        time.sleep(0.8)
        screen = app.primaryScreen()
        pixmap = screen.grabWindow(window.winId())
        path = os.path.join(light_dir, f"{name}.png")
        pixmap.save(path, "PNG")
        kb = os.path.getsize(path) / 1024
        print(f"  light/{name}.png ({kb:.0f} KB)")

    print(f"\nScreenshots guardados en: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
