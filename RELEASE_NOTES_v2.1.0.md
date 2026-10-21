# duAI v2.1.0

Mejoras de estabilidad, seguridad, experiencia de usuario y nuevas funciones virales sobre la base v2.0.

## Novedades

- **Compartir en redes sociales** — Botones reales para Twitter/X, Telegram, WhatsApp y Facebook desde la pestaña Logros y compartir, con el reporte de privacidad preformateado (sin datos sensibles).
- **Exportar analíticas** — Nueva opción en Analíticas para exportar el desglose a CSV o PNG (reutiliza el generador de reportes de imagen).
- **Texto de éxito en blanco** — Todos los mensajes y acentos de éxito/positivo pasaron de verde a blanco para mantener el tema negro puro + letras blancas sin excepciones.
- **Refactor de Ajustes** — `settings_view.py` dividido en `duai/ui/settings/` (6 pestañas: General, Apariencia, Privacidad, Viral, Avanzado, Mantenimiento) sin perder funcionalidad.
- **Animaciones unificadas** — Toda la opacidad/fade centralizada en `ui/animations.py`; eliminado `QGraphicsOpacityEffect` suelto en vistas (evita páginas invisibles).

## Seguridad (hardening)

- **Eliminada ejecución remota de comandos** — La consola ya no pasa input crudo del usuario a PowerShell (se eliminó `_run_powershell` que permitía ejecución arbitraria).
- **Updater robusto** — Renombrado atómico (`os.replace`) y saneo de destino contra path traversal.
- **Auth reforzada** — PBKDF2 600k iteraciones + lockout (5 fallos → 15 min).
- **Scheduler y selfclean** — Privilegios mínimos (`LeastAvailable`) y rutas sin depender de variables de entorno no confiables.

## Calidad

- **CI con GitHub Actions** — `.github/workflows/test.yml` ejecuta smoke, e2e, modules, ui, i18n y el test extendido en cada push a `master` en Windows.
- **Tests extendidos** — `test_e2e_extended.py` cubre pánico con confirmación, updater con SHA-256, scheduler con retry, auto-clean y resolución de todas las claves i18n.
- **i18n completo** — 0 claves faltantes en español e inglés (`i18n_check.py` exit 0).
- **compileall** limpio y 4 suites de pruebas pasando.

## Descargas

| Asset | Descripción |
|-------|-------------|
| `duAI-Setup-2.1.0.exe` | Instalador Inno Setup (51.9 MB) con atajos, desinstalador y auto-inicio |
| `duAI.exe` | Portable (50.0 MB), modo real sin escritura en `%LOCALAPPDATA%` |

Más detalles: `RELEASE_NOTES.md` (histórico v2.0) y `REPORTE_SEGURIDAD_duAI.md` (detalle del hardening v2.1).
