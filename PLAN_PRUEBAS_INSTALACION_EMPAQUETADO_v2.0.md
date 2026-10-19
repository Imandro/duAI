# PLAN DE PRUEBAS — Instalación y Empaquetado v2.0
**duAI** — https://github.com/Imandro/duAI (local: `C:\Users\Zbook de Mario\AppData\Local\Temp\opencode\duAI`)

**Objetivo:** Validar el proceso de construcción y distribución de duAI v2.0 sin modificar ningún archivo de origen.  
**Alcance:** `build_exe.ps1`, `duAI_setup.iss`, `requirements.txt`, `main.py --portable`, PyInstaller e Inno Setup.  
**Condición previa:** NO se ejecuta código. Este plan es accionable para un tester que lo ejecute en un entorno Windows real.

---

## 0. Contexto técnico observado (sin modificar)

| Elemento | Hallazgo relevante para pruebas |
|---|---|
| `build_exe.ps1` | Crea `.venv`, instala `pyinstaller PySide6 pywinpty requests`, genera `assets\duAI.ico` desde `duAI.png` con Pillow, ejecuta PyInstaller `--onefile --noconsole --icon ... --add-data config;config --add-data duai\ui\theme.qss;duai\ui --add-data assets;assets main.py`, salida `dist\duAI.exe`. Opcional Inno Setup (`ISCC duAI_setup.iss`) hacia `installer\duAI-Setup-2.0.0.exe`. |
| `duAI_setup.iss` | AppId fijo, versión `2.0.0`, `PrivilegesRequired=lowest`, `ArchitecturesAllowed=x64`, destinos por defecto `{autopf}\duAI`, tareas: `desktopicon`, `quicklaunchicon`, `autostart` (todas `unchecked`), archivos de `dist\duAI.exe`, `config\*`, `assets\*`, acceso directo grupo + escritorio + quicklaunch, `[Run]` postinstall `nowait skipifsilent`, `[Code]` stub vacío. |
| `main.py` | CLI: `--panic`, `--screenshots`, `--check-updates`, `--portable`. `--portable` solo hace `get_settings().set("portable_mode", True)` y luego lanza la GUI. No hay rama que cambie `base_dir` ni evite escritura en `%LOCALAPPDATA%`. |
| `duai\utils\paths.py` | `base_dir()` hardcodeado a `%LOCALAPPDATA%\duAI` (crea carpeta si no existe). `is_admin()` disponible vía `shell32.IsUserAnAdmin`. |
| `duai\utils\settings.py` | `SettingsStore` lee/escribe `config.json` dentro de `base_dir()`. `save()` traga `OSError` silenciosamente. `portable_mode` es solo una clave más en `config.json`; no redirige el directorio de datos. |
| `duai\utils\logger.py` | `base_dir()` → `%LOCALAPPDATA%\duAI`; `logs_dir()` → `...\logs`; `log()` escribe `duai.log` en modo append. |
| `duai\core\updater.py` | `CURRENT_VERSION = "2.0.0"`, consulta `https://api.github.com/repos/Imandro/duAI/releases/latest`, compara semver básico, descarga el primer asset `.exe`/`.msi`. Bloqueante. `_fetch_json` traga errores de red y devuelve `None` → `result.error = "No se pudo contactar con GitHub."`. |
| `duai\core\selfclean.py` | `purge_all_local_data()` hace `shutil.rmtree(base_dir())`. `purge_logs()` vacía `duai.log`. |
| `duai\core\uninstaller.py` | Lógica para desinstalar apps de IA de terceros (registry Uninstall). No desinstala duAI sí mismo. |
| `requirements.txt` | `PySide6>=6.8`, `pywinpty`, `requests`, `Pillow`. Faltan: `PyInstaller` (solo en script ps1), `setuptools`/`wheel` implícitos, versiones sin pinear. |
| `config\targets.json`, `duai\ui\theme.qss`, `assets\*` | Recursos empaquetados vía `--add-data`. |

---

## 1. Pruebas de empaquetado PyInstaller (`--onefile --noconsole --icon add-data`)

**Build a probar:** salida de `build_exe.ps1` → `dist\duAI.exe` (uno solo, sin consola, con icono).

| ID | Prueba | Pasos (resumen) | Criterio de éxito | Riesgo observado |
|---|---|---|---|---|
| PK-01 | Generación del ejecutable | Ejecutar `build_exe.ps1` en PowerShell con `ExecutionPolicy Bypass` desde raíz del repo. Verificar que se crea `dist\duAI.exe`. | `dist\duAI.exe` existe, tamaño coherente (~tens de MB), salida verde del script. | Si falta Pillow, no se genera el `.ico` y PyInstaller falla por `--icon assets\duAI.ico` ausente. |
| PK-02 | Modo `--onefile` | Ejecutar `dist\duAI.exe` desde una carpeta limpia sin dependencias de Python instaladas en el equipo. | La app arranca y muestra la ventana principal (login / dashboard). No se necesitan DLLs sueltas de Python/PySide6 junto al exe. | PyInstaller onefile extrae a un temp (`_MEIxxxx`) al arrancar; puede ser lento la primera vez y dejar carpeta temp si falla. |
| PK-03 | Modo `--noconsole` | Lanzar `dist\duAI.exe` (doble clic o desde CMD). | No aparece ventana de consola negra (`cmd.exe`/`powershell`) detrás de la GUI. Solo la ventana Qt de duAI. | Sin `--noconsole` se abriría una consola vacía que confunde al usuario. |
| PK-04 | Icono `.ico` aplicado | Verificar propiedades del archivo `dist\duAI.exe` en Explorer (pestaña Detalles / icono) y el icono en la barra de tareas al ejecutar. | El ejecutable muestra el icono `duAI.ico` (no el icono genérico de Python/PyInstaller). | `build_exe.ps1` genera el `.ico` solo si existe `assets\duAI.png`; si falta PNG, advierte y continúa sin icono. |
| PK-05 | `add-data` de `config\targets.json` | Ejecutar portable y navegar a la pestaña Escaneo; verificar que aparecen los objetivos de IA (30+). | Los targets se cargan desde el recurso empaquetado, no falla con "archivo no encontrado". | `--add-data "config;config"` en PyInstaller onefile mapea `config` dentro del bundle; si la ruta en el código usa `__file__` o cwd, puede romper. |
| PK-06 | `add-data` de `duai\ui\theme.qss` | Alternar tema claro/oscuro en Ajustes. | El tema se aplica sin error y el archivo QSS se lee desde el bundle. | `--add-data "duai\ui\theme.qss;duai\ui"` coloca el QSS dentro de `duai/ui` del bundle; si `theme.py` lo lee con ruta relativa al disco, fallará. |
| PK-07 | `add-data` de `assets\` | Verificar que se cargan logos (ventana, bandeja, pánico flotante) y `duAI.png`. | Las imágenes aparecen en la UI; no hay placeholders rotos ni excepciones de archivo faltante. | `--add-data "assets;assets"` copia todo el directorio; verificar que no se omiten subcarpetas si las hubiera. |
| PK-08 | Integridad del bundle | Ejecutar `dist\duAI.exe` en un Windows **sin Python instalado** y sin variables de entorno de Python. | La aplicación arranca completamente (PyInstaller incluye el intérprete y las dependencias). | `pywinpty` y PySide6 tienen dependencias nativas (DLLs) que PyInstaller debe detectar automáticamente; si falta alguna, elexe falla silenciosamente o al abrir la terminal PTY. |
| PK-09 | Tamaño y tiempo de arranque | Medir tamaño de `dist\duAI.exe` y tiempo desde doble clic hasta ventana visible. | Tamaño razonable (< 100 MB esperado por PySide6) y arranque < 10 s en equipo medio. | onefile descomprime en cada arranque; puede ser lento en discos lentos/USB. |
| PK-10 | Limpieza de temp de PyInstaller | Ejecutar y cerrar la app varias veces; inspeccionar `%TEMP%` en busca de carpetas `_MEI*` residuales. | No quedan carpetas `_MEI*` huérfanas tras el cierre normal. | onefile no siempre limpia el temp si el proceso termina de forma abrupta. |

**Entrada/salida esperada de PK-01:** `dist\duAI.exe` + (opcional) `installer\duAI-Setup-2.0.0.exe` si Inno Setup está instalado.

---

## 2. Pruebas del instalador Inno Setup (`duAI_setup.iss`)

**Build a probar:** `installer\duAI-Setup-2.0.0.exe` generado con `ISCC duAI_setup.iss`.

| ID | Prueba | Pasos (resumen) | Criterio de éxito | Riesgo observado |
|---|---|---|---|---|
| IS-01 | Instalación por usuario (solo usuario actual) | Ejecutar instalador sin administrador (o con `PrivilegesRequired=lowest`), elegir "Solo para mí" / `{localappdata}` si la versión de Inno lo permite, o aceptar `{autopf}`. Verificar instalación. | La app se instala, crea acceso directo en Inicio y se puede ejecutar. No requiere elevación de administrador. | `PrivilegesRequired=lowest` intenta instalar sin elevación, pero `{autopf}` (Program Files) normalmente requiere admin. Puede fallar silenciosamente o solicitar UAC. |
| IS-02 | Instalación para todos los usuarios | Ejecutar instalador como administrador, destino `{autopf}\duAI` (Program Files). | Se instala en Program Files, accesible desde todas las cuentas de usuario. | Requiere UAC/admin; si el usuario no es admin, la instalación falla. |
| IS-03 | Atajo en menú Inicio | Después de instalar, abrir menú Inicio y buscar "duAI". | Existe el acceso directo `{group}\duAI` que lanza `duAI.exe`. | `[Icons]` grupo siempre se crea; verificar que apunta a `{app}\duAI.exe`. |
| IS-04 | Atajo en Escritorio | Marcar tarea `desktopicon` durante la instalación. | Aparece acceso directo `duAI` en el escritorio del usuario actual. | Tarea `unchecked` por defecto; el usuario debe marcarla manualmente. |
| IS-05 | Atajo Inicio rápido (Quick Launch) | Marcar tarea `quicklaunchicon`. | Acceso directo en `{userappdata}\Microsoft\Internet Explorer\Quick Launch`. | Quick Launch está obsoleto en Windows 10/11; puede no ser visible. |
| IS-06 | Auto-inicio al iniciar sesión | Marcar tarea `autostart`, instalar, reiniciar sesión (o cerrar y volver a entrar). | duAI se lanza automáticamente al iniciar sesión de Windows. | `[Code]` `InitializeSetup` está vacío (no registra nada en Run/Registro/Tarea programada). La tarea `autostart` solo crea un acceso directo; **no hay implementación real de auto-inicio** en el `.iss` ni en `main.py` (`tarea crear\|quitar` existe en README pero no se ve implementado). **Brecha funcional:** marcar autostart no garantiza arranque automático. |
| IS-07 | Desinstalador limpio | Ir a Panel de Control > Aplicaciones > duAI > Desinstalar (o ejecutar `unins000.exe`). | Se elimina `duAI.exe`, accesos directos, entrada de Panel de Control y carpeta de instalación. No quedan archivos del programa. | `Flags: ignoreversion` en `[Files]`; si el usuario agregó archivos propios en la carpeta de instalación, Inno no los borra (solo los que instaló). Verificar residuos en `%LOCALAPPDATA%\duAI` (config/logs) — Inno no toca `LOCALAPPDATA`, eso lo hace la app o `selfclean`. |
| IS-08 | Entrada de desinstalación en Panel de Control | Tras instalar, verificar "Aplicaciones y características" muestra duAI 2.0.0 con editor Imandro. | Entrada presente, correcta, y desinstalable desde ahí. | `AppId` fijo: si se regenera el instalador con la misma versión, puede entrar en conflicto con instalaciones previas. |
| IS-09 | Rutas con espacios | Instalar en una carpeta personalizada con espacios, ej. `C:\Program Files\Mi Programa\duAI` o `C:\Users\Nombre Usuario\duAI`. | La instalación completa, los accesos directos funcionan y la app se lanza desde esa ruta. | Caminos con espacios en `[Run] postinstall` y accesos directos; Inno los maneja entre comillas, pero verificar que `nowait postinstall skipifsilent` no rompa con espacios. |
| IS-10 | Ejecución automática post-instalación | Finalizar instalación con la casilla "Ejecutar duAI" (marcada por defecto vía `[Run] skipifsilent`). | Se abre la ventana de duAI tras terminar la instalación, sin consola. | `nowait` = no espera a que cierre; `skipifsilent` = salta en modo silencioso `/VERYSILENT`. |
| IS-11 | Instalación silenciosa | Ejecutar `duAI-Setup-2.0.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`. | Instalación sin UI, sin diálogos, acceso directo en Inicio creado. | Verificar que no requiere interacción y que devuelve código de salida 0. |
| IS-12 | Reinstalación sobre versión existente | Instalar 2.0.0 sobre una instalación previa de 2.0.0 (mismo AppId). | Se actualiza/reinstala sin duplicar entradas de desinstalación ni corromper accesos directos. | `AppId` fijo + `ignoreversion`: Inno puede reemplazar o quejarse; validar comportamiento. |

**Nota crítica IS-06 / IS-07:** El instalador **no gestiona `%LOCALAPPDATA%\duAI`** (config.json, logs, quarantine). Esa responsabilidad es de la aplicación (`selfclean`) o del usuario. El desinstalador de Inno solo borra lo que instaló en `{app}`.

---

## 3. Pruebas de modo portable (`--portable`)

**Build a probar:** `dist\duAI.exe --portable` (uno solo, copiado a USB/carpeta extraíble).

| ID | Prueba | Pasos (resumen) | Criterio de éxito | Riesgo observado |
|---|---|---|---|---|
| PT-01 | No escribe en `%LOCALAPPDATA%` | Copiar `dist\duAI.exe` a una carpeta de prueba (simulando USB). Ejecutar `duAI.exe --portable`. Usar la app (ajustes, tema, escaneo). Antes y después, auditar `%LOCALAPPDATA%\duAI\` (config.json, logs, quarantine). | **No se crea ni modifica** `%LOCALAPPDATA%\duAI\config.json`, `logs\duai.log`, ni `quarantine\`. Toda configuración permanece en memoria o en el directorio del exe. | `main.py --portable` solo hace `set("portable_mode", True)` **pero `base_dir()` en `paths.py` y `logger.py` está hardcodeado a `%LOCALAPPDATA%\duAI` y se crea al importar**. `get_settings().save()` escribirá `config.json` en `%LOCALAPPDATA%\duAI\` **aunque sea portable**. **Brecha crítica: `--portable` no evita escritura en LOCALAPPDATA.** |
| PT-02 | Ejecución desde USB/unidad extraíble | Copiar el exe a una unidad USB (o unidad de red/extraíble con letra de unidad distinta), ejecutar `--portable`. | Arranca y funciona desde la unidad extraíble; no requiere instalación; no deja dependencias en el equipo anfitrión (salvo lo que el propio Windows haga). | onefile extrae a `%TEMP%\_MEI*` al arrancar (deja huella temporal). El tema/icono se cargan del bundle. |
| PT-03 | Persistencia portable (opcional) | Ejecutar `--portable`, cambiar tema, cerrar, volver a abrir `--portable` desde la misma carpeta. | Verificar si la preferencia se conserva (ideal: en un `config.json` junto al exe, no en LOCALAPPDATA). | Dado que `base_dir()` es fijo a LOCALAPPDATA, la preferencia se escribiría ahí, rompiendo la promesa de portable. |
| PT-04 | Modo sigilo / selfclean desde portable | Activar modo sigilo y `autoexit`, cerrar la app. | Si `selfclean` apunta a `base_dir()`, borraría `%LOCALAPPDATA%\duAI` incluso en portable. Verificar comportamiento. | `selfclean.purge_all_local_data()` usa `base_dir()` = LOCALAPPDATA. En portable esto borraría datos del usuario anfitrión, no del USB. |
| PT-05 | Portable sin conexión | Ejecutar `--portable` en equipo sin red. | Arranca sin intentar contactar GitHub (salvo si el usuario pide `--check-updates` o settings `check_updates=True` al arranque). | `app.py` llama `check_for_updates_async` si `should_check_on_startup()` es True; en portable sin red, el hilo falla silenciosamente (no bloquea). |

**Recomendación de prueba:** Para PT-01, usar Sysinternals Process Monitor o `dir` antes/después en `%LOCALAPPDATA%\duAI`.

---

## 4. Casos límite (edge cases)

| ID | Prueba | Pasos (resumen) | Criterio de éxito | Riesgo observado |
|---|---|---|---|---|
| EC-01 | Sin permisos de administrador | Ejecutar instalador y portable como usuario estándar (no admin). | Portable: arranca y funciona salvo funciones que requieran admin (hosts, prefetch). Instalador: si destino es `LOCALAPPDATA`, funciona; si es `Program Files`, falla o pide UAC. | `is_admin()` existe en `paths.py` pero no se usa para bloquear/advertir en funciones de admin. `hosts_block` requiere escribir `C:\Windows\System32\drivers\etc\hosts` → falla silenciosamente sin admin. |
| EC-02 | Archivos `hosts` bloqueado / inaccesible | Activar `hosts si` (bloqueo de telemetría) o dejar el archivo hosts de Windows bloqueado por otro proceso/antivirus. | duAI no se bloquea; informa o ignora el error de hosts; el resto de funciones funcionan. | Escritura a hosts sin admin o con archivo bloqueado lanza excepción; verificar que no cae la app. |
| EC-03 | Navegador abierto bloqueando limpieza | Abrir Chrome/Edge con pestañas de IA, ejecutar escaneo y limpieza de navegador. | duAI detecta el proceso del navegador, lo marca como BLOQUEADO, lo salta y continúa con otros targets. No cierra el navegador del usuario sin consentimiento. | `paths.is_process_running` y `running_conflicts` existen; verificar que la UI muestra "BLOQUEADA" y no falla. |
| EC-04 | Disco lleno | Llenar el disco destino (o cuota) hasta que no se pueda escribir. Ejecutar portable e intentar guardar configuración / hacer limpieza. | La app no falla de forma catastrófica; `settings.save()` traga `OSError`; logs fallan silenciosamente; limpieza informa error de espacio. | `settings.save()` y `logger.log()` tragan `OSError` (silencioso). El usuario no sabrá que la configuración no se guardó. |
| EC-05 | Versión antigua de Windows | Ejecutar instalador y portable en Windows 10 (o Windows 7 si se soporta) — notar que `ArchitecturesAllowed=x64` y PySide6 requieren Windows 10/11. | En Windows 10 64 bits: funciona. En Windows 7/8: debe fallar de forma clara o no instalarse. | El README dice "Windows 10/11". PySide6 6.8+ no soporta Windows 7/8. Verificar que el instalador no permita instalación en SO no soportado (o que avise). |
| EC-06 | Ejecutable desde ruta con caracteres especiales / unicode | Copiar `dist\duAI.exe` a `C:\Pruebas duAI (test)\app.exe` y ejecutar. | Arranca correctamente. | PyInstaller onefile y paths con paréntesis/espacio pueden causar problemas de extracción al temp. |
| EC-07 | Ejecutar dos instancias simultáneas | Lanzar `duAI.exe` dos veces. | Segunda instancia: o se rechaza (single instance) o abre ventana separada sin corromper config. | No se ve mecanismo de single-instance en `main.py`; posible corrupción de `config.json` por escritura concurrente (`SettingsStore` tiene lock solo intra-proceso, no inter-proceso). |
| EC-08 | Antivirus / SmartScreen bloquea el exe | Ejecutar `dist\duAI.exe` sin firmar en Windows con SmartScreen activado. | Windows muestra aviso ("Protejo al equipo") pero permite ejecutar tras "Más información" o el usuario puede confirmar. | Un exe de PyInstaller no firmado suele disparar SmartScreen/heurísticas de AV. No hay mitigación en el build. |
| EC-09 | Pantalla de alta DPI / escalado | Ejecutar con escalado 125%, 150%, 200% en Windows. | La UI de PySide6 se renderiza sin recortes ni elementos ilegibles. | PySide6 maneja DPI, pero verificar que la ventana fija `LoginDialog(360x200)` sea usable. |
| EC-10 | Cierre inesperado / kill del proceso | Matar `duAI.exe` desde el Administrador de tareas mientras escanea/limpia. | No quedan locks de archivo que impidan reiniciar; al volver a abrir no corrompe `config.json`. | Limpieza interrumpida puede dejar archivos en cuarentena o logs parciales. |

---

## 5. Pruebas de actualización (`--check-updates`)

**Build a probar:** `dist\duAI.exe --check-updates` y pestaña Actualizaciones de la GUI.

| ID | Prueba | Pasos (resumen) | Criterio de éxito | Riesgo observado |
|---|---|---|---|---|
| UP-01 | Sin internet | Desconectar red (o firewall bloquea GitHub), ejecutar `--check-updates`. | Muestra error claro: "No se pudo contactar con GitHub" y sale con código 1. No cuelga indefinidamente. | `_fetch_json` tiene `timeout=15`; sin red tarda hasta el timeout. `check_for_updates_async` en GUI corre en hilo daemon, no bloquea la ventana. |
| UP-02 | Descarga fallida | Simular URL inválida o cortar red durante `download_update`. | `download_update` devuelve `False`; la GUI informa error de descarga; no deja archivo parcial corrupto como "instalador listo". | `download_update` abre `dest_path` en modo `"wb"`; si falla a la mitad, deja archivo parcial. No hay verificación de hash/firma del descargado. |
| UP-03 | Versión ya actual | Con internet, versión instalada = 2.0.0 y latest = 2.0.0 (o menor). | Muestra: "duAI está actualizado (versión 2.0.0)". No ofrece descarga. | Comparación semver básica: `latest_parts > current_parts`. Versiones como `2.0.0-beta` o `2.0` romperían el parseo `int(x)`. |
| UP-04 | Nueva versión disponible | Con internet, latest > 2.0.0. | Muestra "Nueva versión disponible: X.Y.Z (actual: 2.0.0)" + URL de descarga. El usuario decide si instala. | El asset seleccionado es el primer `.exe`/`.msi` del release; si GitHub publica varios, podría elegir el equivocado (instalador vs portable). No distingue portable de instalador en el asset. |
| UP-05 | `--check-updates` sale con código correcto | Ejecutar desde PowerShell y capturar `$LASTEXITCODE`. | Error de red → código 1. Actualizado → 0. Nueva versión → 0. | Verificar que `return 1` solo cuando `result.error`; si hay versión nueva pero no error, retorna 0 (correcto). |
| UP-06 | Actualización silenciosa / automática | Verificar si hay algún mecanismo de auto-instalación tras descarga. | **No debe instalarse automáticamente sin consentimiento.** duAI solo informa y da URL; el usuario ejecuta el instalador. | No se observa auto-instalación en el código (bueno). Verificar que no se intente ejecutar el descargado silenciosamente. |

---

## 6. Dependencias faltantes o incorrectas en `requirements.txt`

**Archivo actual (`requirements.txt`):**
```
PySide6>=6.8
pywinpty
requests
Pillow
```

### 6.1 Faltantes (usados en el build / runtime y no declarados)

| Dependencia | ¿Por qué falta? | Impacto si no está |
|---|---|---|
| `pyinstaller` | Usado en `build_exe.ps1` (`& $venvPython -m pip install --quiet pyinstaller ...`), pero no está en `requirements.txt`. | Quien intente reproducir el build solo con `pip install -r requirements.txt` no tendrá PyInstaller y `build_exe.ps1` lo instala de forma aparte (duplicación de fuente de verdad). |
| `setuptools`, `wheel` | Implícitos para construcción de paquetes y PyInstaller. | Puede faltar en entornos mínimos. |
| `pywin32` (o `pypiwin32`) | `paths.py` usa `ctypes.windll` (no necesita paquete), pero partes de PySide6/pywinpty en Windows se benefician. No es estrictamente faltante por ctypes. | Bajo. |
| `pkg-resources` / `importlib-metadata` | Para lectura de versión/recursos en el bundle onefile. | Puede ser necesario en tiempo de ejecución del exe. |

### 6.2 Incorrectas / riesgosas

| Dependencia | Problema | Recomendación |
|---|---|---|
| `PySide6>=6.8` | Versión mínima sin pin superior. PySide6 6.8+ requiere **Windows 10/11** y Python ≥3.8; si se instala una versión futura mayor (6.9, 7.0) puede haber cambios rotos en Qt. | Pinear versión probada, ej. `PySide6==6.8.x` o `>=6.8,<7`. |
| `pywinpty` | Sin versión. En Python 3.14 (según README) puede no haber wheel de `pywinpty` disponible o requerir compilación. | Pinear a una versión con wheel para la versión de Python usada. |
| `requests` | Solo usado por el updater? En `updater.py` se usa `urllib`, no `requests`. `requests` está en requirements pero `updater.py` usa `urllib.request`. | `requests` puede ser innecesaria (muerta) o usarse en otro módulo no revisado. Verificar uso real. |
| `Pillow` | Solo usada en `build_exe.ps1` para generar el `.ico`; no se usa en runtime. | Es dependencia de **build**, no de runtime. No debería ir en `requirements.txt` del usuario final, o separar en `requirements-build.txt`. |
| (ausente) `pyinstaller` | Build-time, no runtime. | Mover a `requirements-build.txt` o documentar aparte. |

### 6.3 Resumen de acción para requirements.txt

- Separar dependencias de **runtime** (`PySide6`, `pywinpty`, `requests` si se usa) de **build** (`PyInstaller`, `Pillow`).
- Pinear versiones probadas para reproducibilidad del build v2.0.
- Verificar si `requests` se importa realmente en algún módulo de `duai/`; si no, eliminarla.

---

## 7. Matriz de ejecución sugerida (orden recomendado)

1. **PK-01** → generar `dist\duAI.exe` (bloqueante para el resto).
2. **PK-02..PK-10** → validar el exe portable uno-archivo.
3. **PT-01..PT-05** → validar `--portable` (especialmente PT-01: escritura en LOCALAPPDATA).
4. **IS-01..IS-12** → generar y validar el instalador Inno Setup (requiere ISCC instalado).
5. **EC-01..EC-10** → casos límite sobre portable e instalador.
6. **UP-01..UP-06** → validar `--check-updates`.
7. **Sección 6** → auditoría de `requirements.txt` (estática, sin ejecutar).

---

## 8. Hallazgos críticos (bloqueantes / brechas) detectados al revisar el código

| # | Área | Hallazgo | Impacto |
|---|---|---|---|
| C1 | Modo portable | `main.py --portable` solo setea `portable_mode=True` pero **no redirige `base_dir()`**; `duai\utils\logger.py` y `paths.py` siguen escribiendo en `%LOCALAPPDATA%\duAI`. | **El modo portable no cumple su promesa de "no escribir en LOCALAPPDATA".** |
| C2 | Auto-inicio | `duAI_setup.iss` tiene tarea `autostart` pero `[Code]` está vacío y no hay registro en Run/Tarea programada. | Marcar "Ejecutar duAI al iniciar sesión" no produce auto-inicio real. |
| C3 | Uninstaller | `duai\core\uninstaller.py` desinstala apps de IA de **terceros**, no a duAI mismo. El desinstalador es el de Inno Setup (`unins000.exe`). | No hay autodesinstalación de duAI desde la app; residuos en `LOCALAPPDATA` quedan tras desinstalar. |
| C4 | SmartScreen | `dist\duAI.exe` no está firmado. | Alertas de Windows/aviros en primera ejecución; fricción de instalación. |
| C5 | requirements.txt | `Pillow` y `PyInstaller` son de build, no runtime. `requests` quizá no usada (`updater.py` usa `urllib`). Versiones sin pinar. | Reproducibilidad del build y tamaño de dependencias del usuario final. |
| C6 | `--check-updates` sin red | `_fetch_json` timeout 15 s; sin internet demora y devuelve error. | Aceptable, pero verificar que no bloquee la GUI (usa hilo daemon, OK). |
| C7 | `AppId` fijo en Inno Setup | Mismo GUID para todas las versiones. | Reinstalación/actualización sobre misma versión puede comportarse de forma inesperada; cambiar AppId por versión mayor. |

---

**Fin del plan.** Este documento es solo de planificación y auditoría; no se modificó ningún archivo del repositorio.