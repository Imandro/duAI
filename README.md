<p align="center">
  <img src="assets/duAI.png" alt="duAI Logo" width="300">
</p>

<h1 align="center">duAI — Don't Use AI</h1>

<p align="center">
  Herramienta de privacidad para Windows que detecta y elimina todos los rastros que las herramientas de IA dejan en tu computadora.
</p>

<p align="center">
  <strong>100% local. Sin telemetria. Sin cuentas. Sin conexion externa.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%2F11-black?style=flat-square" alt="Windows">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/Licencia-MIT-green?style=flat-square" alt="MIT">
</p>

---

## Descarga

| | |
|---|---|
| **Exe portable** | [duAI.exe](https://github.com/Imandro/duAI/blob/master/dist/duAI.exe) — sin instalacion, copiable a USB |
| **Codigo fuente** | [github.com/Imandro/duAI](https://github.com/Imandro/duAI) |
| **Requisitos** | Windows 10/11, Python 3.10+ (solo para ejecutar desde codigo) |

---

## Que hace duAI

duAI escanea tu equipo y encuentra **todo** lo que las apps de IA dejan detras:

- **Apps de escritorio**: ChatGPT, Claude, Copilot, Cursor, Windsurf, Ollama, LM Studio, GPT4All, Perplexity
- **Herramientas CLI**: OpenCode, Codex, Claude Code, Aider, HuggingFace, Jan, Continue
- **Navegadores**: historial de IA en Chrome, Edge, Brave, Firefox (borra solo sitios de IA, conserva lo demas)
- **Registro de Windows**: UserAssist, MuiCache, RunMRU, MRULists
- **DNS y portapapeles**: cache DNS real, dominios de telemetria, historial de copias
- **Cronologia y ubicacion**: Windows Timeline, datos de ubicacion
- **Temp y prefetch**: archivos temporales y prefetched

### Escaneo paralelo

duAI escanea **6 objetivos simultaneamente** con ThreadPoolExecutor. Muestra progreso en tiempo real con barra de progreso, tiempo transcurrido y boton de cancelar.

### Modos de limpieza

| Modo | Que hace |
|---|---|
| **Papelera** | Envia archivos a la papelera de reciclaje (reversible) |
| **Cuarentena** | Mueve archivos a una carpeta segura con manifesto, restaurable en cualquier momento |
| **Permanente** | Borrado definitivo sin posibilidad de recuperacion |

---

## Interfaces

### Temas puros

Alterna entre **todo blanco** y **todo negro** con un clic. Sin mezclas, sin grises.

- Boton en el sidebar
- Comando: `tema claro` / `tema oscuro`
- Se guarda y restaura al reiniciar

### Animaciones

- Fade de arranque (ventana aparece de negro)
- Transiciones suaves entre pestanas
- Cajon de comandos se despliega/oculta con slide
- Cambio de tema con dip de opacidad
- Contadores animados en el dashboard
- Pulso continuo en el boton de panico

### Boton de panico flotante

Widget always-on-top que se puede arrastrar por la pantalla:

- Click izquierdo: ejecuta panico
- Click derecho: abrir duAI / ocultar widget / salir
- Activalo con `widget si` o desde el menu de la bandeja
- Persiste su posicion entre sesiones

---

## Pestanas

| Pestana | Funcion |
|---|---|
| **RESUMEN** | Dashboard con stats animados, acceso rapido a escaneo y limpieza |
| **ESCANEO** | Tabla de 30+ objetivos con progreso paralelo, estado, tamano, exportacion TXT/CSV |
| **LIMPIEZA** | Seleccion granular, vista previa, cuarentena, delta antes/despues |
| **SESION** | Navegacion IA en perfil temporal + sesiones CLI seguras con sandbox |
| **PANICO** | Limpieza total silenciosa con destino configurable |
| **AJUSTES** | Contrasena, exclusiones, modo sigilo, cuarentena, hosts, programador |
| **TERMINAL** | Consola PTY real con integracion de herramientas CLI aisladas |

---

## Sesiones CLI seguras

Ejecuta herramientas de IA de consola en un **entorno aislado**. Todo lo que escriban queda dentro del sandbox. Al terminar, se borran los rastros automaticamente.

### Herramientas soportadas

| Herramienta | Comando | Que hace |
|---|---|---|
| **OpenCode** | `opencode` | Terminal AI interactiva |
| **Claude Code** | `claude` | Asistente de codigo de Anthropic |
| **Codex CLI** | `codex` | Terminal AI de OpenAI |
| **Gemini CLI** | `gemini` | Terminal AI de Google |
| **Aider** | `aider` | Pair programming con IA |

### Como funciona

1. Selecciona la herramienta en la pestana SESION o TERMINAL
2. Elige la carpeta de trabajo (opcional)
3. Se crea un sandbox temporal con entorno aislado
4. La herramienta corre con `USERPROFILE`, `APPDATA`, `HOME`, `XDG_*` redirigidos al sandbox
5. Al salir: borrado del sandbox + purga de historial PowerShell
6. Sandboxes huérfanos se limpian automáticamente al arrancar duAI

```
PS> (duAI sandbox) C:\Users\you\project> opencode
PS> (duAI sandbox) C:\Users\you\project> claude
```

---

## Terminal PTY

duAI incluye un terminal real (PTY) que puede ejecutar cualquier app de consola:

- **Pestana TERMINAL** — PowerShell completo con output en vivo
- **Cajon CLI inferior** — escribe comandos directamente, los no-duAI se ejecutan en PowerShell
- Soporta apps interactivas: `opencode`, `claude`, `codex`, `gemini cli`, etc.

```
PS> opencode
PS> claude
PS> gemini
PS> Get-Process
PS> dir
```

---

## Comandos CLI

| Comando | Descripcion |
|---|---|
| `ayuda` | Lista todos los comandos |
| `escanear [filtro]` | Escanea y abre pestana ESCANEO |
| `limpiar <sel>` | Limpia: `todo`, `apps`, `navegador`, `sistema`, o IDs |
| `panico` | Limpieza total silenciosa |
| `sesion <sitio>` | Abre ChatGPT/Claude/Gemini en perfil temporal |
| `apps` | Lista apps de IA instaladas |
| `desinstalar <app>` | Desinstala una app de IA |
| `tema claro\|oscuro` | Cambia el tema |
| `widget si\|no` | Activa/desactiva el boton flotante |
| `exportar txt\|csv` | Exporta el ultimo escaneo |
| `destino <modo>` | Cambia papelera/cuarentena/permanente |
| `excluir <id>` / `permitir <id>` | Gestiona exclusiones |
| `contrasena <clave>` | Establece contrasena de acceso |
| `sigilo si\|no` | Activa modo sigilo |
| `autoexit si\|no` | Limpieza automatica al cerrar |
| `intervalo <min>` | Limpieza periodica |
| `hotkey si\|no` | Tecla global Ctrl+Alt+D |
| `hosts si\|no` | Bloqueo de telemetria via hosts |
| `tarea crear\|quitar` | Tarea de Windows al iniciar sesion |
| `cuarentena ver\|restaurar\|vaciar` | Gestiona cuarentena |
| `cerrarpestañas` | Cierra pestañas de IA en navegadores Chromium |
| `terminal [comando]` | Abre la terminal PTY o ejecuta un comando |
| `purgarlogs` | Vacia bitacora y accesos recientes |
| `salir` | Cierra duAI |

---

## Atajos

| Atajo | Accion |
|---|---|
| `Ctrl+Alt+D` | Ejecuta panico (si esta activo en Ajustes) |
| Click en bandeja | Abre duAI |
| Doble-click en bandeja | Abre duAI |

---

## Instalacion (desde codigo)

```powershell
git clone https://github.com/Imandro/duAI.git
cd duAI
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

### Panico silencioso (sin interfaz)

```powershell
.venv\Scripts\python main.py --panic
```

### Generar exe portable

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

Genera `dist\duAI.exe` — un unico archivo sin dependencias.

---

## Seguridad

- **Destino por defecto**: papelera de reciclaje (no borra nada permanentemente sin que lo pidas)
- **Vista previa activada**: en la pestana LIMPIEZA siempre ves que se va a borrar antes de ejecutar
- **Objetivos bloqueados**: si una app esta corriendo, duAI la marca como BLOQUEADA y la salta
- **Permisos**: PREFETCH y HOSTS requieren administrador; se omiten si no los hay
- **Catalogo extensible**: edita `config/targets.json` para agregar o quitar objetivos
- **PBKDF2**: la contrasena se almacena con hash, no en texto plano
- **Sesiones aisladas**: las herramientas CLI corren en sandbox con env vars redirigidas

---

## Privacidad de la propia herramienta

duAI no tiene telemetria, no abre conexiones de red y no guarda rastros de su propio uso.

Los unicos archivos que crea:

| Archivo | Contenido |
|---|---|
| `%LOCALAPPDATA%\duAI\config.json` | Preferencias y hash de contrasena |
| `%LOCALAPPDATA%\duAI\logs\duai.log` | Bitacora local de acciones |
| `%LOCALAPPDATA%\duAI\quarantine\` | Solo si usas cuarentena restaurable |
| `%LOCALAPPDATA%\duAI\cli_sandbox\` | Temporal — se borra al salir de sesiones CLI |

Con **modo sigilo** activo, la bitacora se vacia automaticamente en cada cierre. Desde Ajustes puedes eliminar todos los datos de duAI con un boton.

---

## Tecnologia

- **Python 3.14** + **PySide6** (Qt6)
- Temas propios con sistema de paletas (sin dependencias de estilos)
- Animaciones via QPropertyAnimation (sin dependencias extra)
- **pywinpty** para terminal PTY real
- **ThreadPoolExecutor** para escaneo paralelo
- **SQLite read-only** para conteo real de visitas a sitios de IA
- PyInstaller para exe portable
- 25+ tests unitarios

---

<p align="center">
  <img src="assets/duAI_white.png" alt="duAI Logo Dark" width="200">
</p>

## Licencia

MIT

---

<p align="center">
  <strong>by <a href="https://github.com/Imandro">Imandro</a></strong>
</p>
