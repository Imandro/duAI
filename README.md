# duAI — Don't Use AI

Herramienta de escritorio para Windows orientada a la privacidad total del usuario.
duAI detecta y elimina los rastros que las herramientas de inteligencia artificial
dejan en tu computadora: datos, ubicacion, conversaciones y cualquier evidencia de uso de IA.

Todo el procesamiento es **local**. duAI no tiene telemetria, no abre conexiones de red
(mas alla de vaciar la cache DNS local) y no guarda rastros de su propio uso.

## Caracteristicas

- **Detector de rastros**: escanea tu equipo y muestra que rastros de IA existen,
  con tamano, cantidad de elementos y estado de cada objetivo.
- **Limpieza selectiva**: aplicaciones de IA de escritorio (ChatGPT, Claude, Copilot,
  Cursor, Windsurf, Ollama, LM Studio, GPT4All, Perplexity), navegadores (Chrome,
  Edge, Brave, Firefox) y sistema (temporales, recientes, registro, DNS, portapapeles,
  cronologia, ubicacion).
- **Historial quirurgico**: en Chrome/Edge/Brave/Firefox elimina solo las visitas a
  sitios de IA (chatgpt.com, claude.ai, gemini.google.com, perplexity.ai, etc.)
  conservando el resto de tu historial.
- **Modo panico**: un boton que ejecuta limpieza total silenciosa. Tecla global
  `Ctrl+Alt+D`, icono en bandeja y auto-limpieza al cerrar o por intervalo.
- **Sesion protegida**: abre ChatGPT, Claude, Gemini, Perplexity, Copilot, Poe o
  DeepSeek en un perfil temporal aislado del navegador; al cerrar, el perfil se
  destruye por completo. Tu perfil real nunca toca la web de IA.
- **Cuarentena restaurable**: ademas de papelera y borrado permanente, los rastros
  pueden moverse a cuarentena y restaurarse despues si te arrepientes.
- **Comparacion antes/después**: tras cada limpieza real se muestra el delta de
  elementos y espacio liberado, incluida la estadistica LIBERADO ESTA SESION.
- **Modo sigilo**: purga automatica de la propia bitacora de duAI y sus accesos
  recientes al cerrar, o borrado total de todos sus datos locales desde Ajustes.
- **Programador de Windows**: tarea opcional de limpieza en cada inicio de sesion.
- **Bloqueo de telemetria**: redirige dominios de telemetria de IA via archivo hosts.
- **Contrasena local**: acceso protegido con PBKDF2, sin cuentas ni nube.
- **Reportes**: exportacion TXT/CSV del escaneo y de la comparacion antes/despues.

## Ejecutable portable (opcional)

Genera `dist\duAI.exe`, un unico archivo sin instalacion, ideal para USB:

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

## Instalacion

Requiere Python 3.10 o superior.

```powershell
cd Desktop\duAI
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Uso

```powershell
.venv\Scripts\python main.py
```

Modo panico silencioso (sin interfaz):

```powershell
.venv\Scripts\python main.py --panic
```

### Pestañas

| Pestana | Funcion |
|---|---|
| RESUMEN | Estado general, rastros detectados y espacio liberado |
| ESCANEO | Detector de rastros con detalle por objetivo y exportacion |
| LIMPIEZA | Seleccion granular, vista previa, cuarentena y delta antes/despues |
| SESION | Navegacion IA con perfil temporal destruido al cerrar |
| PANICO | Limpieza total, modo de destino, auto-limpieza, intervalo y hotkey |
| AJUSTES | Contrasena, exclusiones, modo sigilo, cuarentena, hosts, programador |

## Notas de seguridad

- Por defecto la limpieza envia archivos a la **papelera de reciclaje**; el modo
  permanente es opcional.
- Los objetivos con procesos abiertos se marcan como BLOQUEADOS: cierra la aplicacion
  correspondiente antes de limpiarla.
- PREFETCH y el archivo HOSTS requieren permisos de administrador.
- La vista previa esta activada por defecto en la pestana LIMPIEZA.
- El catalogo de objetivos es extensible editando `config/targets.json`.

## Privacidad de la propia herramienta

Los unicos archivos que duAI crea son:

- `%LOCALAPPDATA%\duAI\config.json` — preferencias y hash de contrasena.
- `%LOCALAPPDATA%\duAI\logs\duai.log` — bitacora local de acciones.
- `%LOCALAPPDATA%\duAI\quarantine\` — solo si usas la cuarentena restaurable.

Con el modo sigilo activo, la bitacora se vacia en cada cierre. Desde Ajustes puedes
eliminar todos los datos de duAI con un boton.
