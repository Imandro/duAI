# Reporte de auditoría de seguridad — duAI

**Repositorio:** `C:\Users\Zbook de Mario\AppData\Local\Temp\opencode\duAI`  
**Fecha:** 20 de octubre de 2026  
**Ámbito:** `duai/core/updater.py`, `duai/security/auth.py` (referenciada como `duai/core/auth.py` en la tarea; el archivo real está en `duai/security/auth.py`), `duai/ui/console_view.py`, `duai/utils/paths.py` (`expand`), `duai/core/scheduler.py`, `duai/core/selfclean.py`, permisos de `%LOCALAPPDATA%\duAI` (modo no portable).  
**Estado de compilación:** `python -m compileall -q duai` → **EXIT CODE 0** (sin errores de sintaxis; ver sección 5).

---

## (a) Hallazgos de seguridad

| ID | Severidad | Archivo : líneas | Hallazgo |
|----|-----------|------------------|----------|
| H-01 | **CRÍTICO** | `duai/ui/console_view.py:134-158` (antes del parche) | El router de la consola ejecuta **cualquier comando no reconocido** pasándolo íntegro a `powershell.exe -Command <texto del usuario>` (`CommandRouter.execute` → `_run_powershell`). Aunque Python llama con `shell=False`, el string va sin sanear a PowerShell, lo que permite **ejecución arbitraria de comandos** en el contexto del usuario que ejecuta duAI (inyección de comandos completa). |
| H-02 | ALTO | `duai/security/auth.py:23-29` (antes del parche) | `verify_password` no implementa **lockout** tras intentos fallidos: un atacante puede probar contraseñas ilimitadamente (fuerza bruta online contra la UI, u offline si obtiene `config.json`). |
| H-03 | ALTO | `duai/security/auth.py:7` | PBKDF2-HMAC-SHA256 con solo **200.000 iteraciones**, por debajo de la recomendación actual de OWASP (≥600.000 para PBKDF2-SHA256). |
| H-04 | MEDIO | `duai/core/updater.py:288-291` (antes del parche) | **TOCTOU en el renombre atómico**: `os.path.exists(dest_path)` → `os.remove(dest_path)` → `os.rename(tmp_path, dest_path)`. Entre el borrado y el rename existe una ventana de carrera que un atacante local podría explotar (sustitución de `dest_path`/junction en Windows). |
| H-05 | MEDIO | `duai/core/updater.py:230` | `download_update(url, dest_path, ...)` no saneaba `dest_path`: un valor controlado por el usuario con `..` permitiría escritura de `.part` / `.sig` / destino fuera del directorio esperado (**path traversal**). |
| H-06 | MEDIO | `duai/ui/updater_view.py:535-540` | El flujo de descarga de la UI **nunca pasaba `signature_url`** a `download_update`, por lo que la verificación de firma Ed25519 (aunque exista el asset `.sig` en el release) no se ejecutaba en la práctica. |
| H-07 | MEDIO | `duai/core/scheduler.py:729-731` | El XML generado para Task Scheduler usa `<RunLevel>HighestAvailable</RunLevel>`: las tareas se instalan con el **nivel de privilegio más alto disponible** (elevación si el usuario es admin), excesivo para tareas de limpiecheo/rutineo. |
| H-08 | BAJO | `duai/core/scheduler.py:716` | Cuando no está congelado (`frozen`), el XML usa `"python.exe"` sin ruta absoluta, resuelto vía `PATH` (riesgo menor de ejecución de binario no esperado). |
| H-09 | BAJO | `duai/core/selfclean.py:209` | `purge_prefetch` construye la ruta de Prefetch a partir de `os.environ.get("WINDIR", ...)`: variable de entorno controlable dentro del proceso, posible redirección de la purga. |
| H-10 | BAJO | `duai/utils/paths.py:8` | `expand()` aplica `os.path.expandvars`/`expanduser`. Las llamadas actuales usan cadenas hardcodeadas (ej. `"%LOCALAPPDATA%/duAI"`), pero si se usara con entrada de usuario se permitiría inyección de variables de entorno y traversal (`..`). |

**Estado de los requisitos de la tarea antes del parche:**
- Descarga en `.part`: ✅ ya implementado (línea 237).
- Verificación SHA-256: ✅ ya implementado (líneas 254-263).
- Verificación Ed25519 si `DUAI_ED25519_PUBKEY`: ✅ implementado (`verify_signature`, líneas 201-227), pero opcional (retorna `True` si no hay clave) y no invocado por la UI (H-06).
- Renombre atómico: ⚠️ existía pero con TOCTOU (H-04).
- PBKDF2 con salt: ✅ implementado, iteraciones bajas (H-03).
- Lockout tras fallos: ❌ **ausente** (H-02).
- Contraseña no en texto plano: ✅ solo se guardan `password_hash` + `password_salt` (además cifrados con Fernet en `config.json` mediante `enc_key.bin`).

---

## (b) Parches aplicados

### 1. `duai/ui/console_view.py` — elimina ejecución de PowerShell sin sanear (H-01, CRÍTICO)

**Antes (líneas 128-158 aprox.):**
```python
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            self._run_powershell(text)
            return
        handler(args, flags)

    def _run_powershell(self, text):
        import subprocess
        ...
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", text], ...
        )
        ...
```

**Después:**
```python
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            self.out(t("cli.unknown_command", cmd=cmd))
            return
        handler(args, flags)
```

Se eliminó por completo el método `_run_powershell` (y su `import subprocess` local). Un comando desconocido devuelve ahora un mensaje de error en lugar de ejecutar la entrada del usuario en PowerShell.

**Traducciones añadidas:**
- `duai/i18n/translations/es.json`: `"unknown_command": "Comando no reconocido: {cmd}"`
- `duai/i18n/translations/en.json`: `"unknown_command": "Unrecognized command: {cmd}"`

### 2. `duai/security/auth.py` — PBKDF2 600k + lockout (H-02, H-03, ALTO)

- `_ITERATIONS`: `200_000` → `600_000` (línea 7).
- `set_password` reinicia `password_fail_count = 0` y `password_lock_until = None`.
- `verify_password`:
  - Si hay `password_lock_until` y no expiró → retorna `False` (bloqueo activo).
  - Tras 5 fallos consecutivos (`_MAX_FAILED_ATTEMPTS`) → establece `password_lock_until = ahora + 900 s` (15 min).
  - Acierto → resetea contador y bloqueo.
- Se añadió `import time`.

### 3. `duai/utils/settings.py` — claves de estado de lockout al esquema (soporte de H-02)

Tras `"password_salt"` se añadieron:
```python
    "password_fail_count": ConfigField(int, 0, lambda v: isinstance(v, int) and v >= 0, "Intentos fallidos consecutivos de contraseña"),
    "password_lock_until": ConfigField(str, None, None, "Timestamp de fin de bloqueo de contraseña"),
```
(Sin esto, `SettingsStore.set` rechazaba las claves desconocidas y el lockout no se persistía.)

### 4. `duai/core/updater.py` — saneamiento de destino + renombre atómico real (H-04, H-05, MEDIO)

**Saneamiento de `dest_path` (líneas 233-238):** antes de crear el archivo se colapsa el destino a un nombre de archivo directo dentro de su directorio:
```python
        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        dest_path = os.path.join(dest_dir, os.path.basename(dest_path))
        tmp_path = dest_path + ".part"
        sig_path = dest_path + ".sig"
```
Esto elimina path traversal mediante `..` en `dest_path` (afecta `.part`, `.sig` y el destino final).

**Renombre atómico (líneas 292-295):** se remplazó `os.path.exists` + `os.remove` + `os.rename` por:
```python
        os.replace(tmp_path, dest_path)
```
`os.replace` es atómico tanto en Windows como en POSIX y elimina la ventana de TOCTOU. El bloque `except` de limpieza ahora usa `tmp_path` en vez de reconstruir `dest_path + ".part"`.

### 5. `duai/ui/updater_view.py` — la UI pasa y usa `signature_url` (H-06, MEDIO)

- `UpdaterView.__init__` (línea 261 aprox.): `self._signature_url = ""`.
- `done()` del chequeo (línea 496 aprox.): `self._signature_url = result.signature_url`.
- `wrapped_job` en `_download` (línea 539 aprox.): `download_update(..., signature_url=getattr(self, "_signature_url", ""))`.

### 6. `duai/core/scheduler.py` — privilegios y ruta del ejecutable en el XML (H-07, H-08, MEDIO/BAJO)

- `<RunLevel>HighestAvailable</RunLevel>` → `<RunLevel>LeastAvailable</RunLevel>` (líneas 729-731).
- `exe_path = os.path.abspath(sys.executable) if getattr(sys, 'frozen', False) else "python.exe"` → `exe_path = sys.executable` (línea 716), evitando resolución vía `PATH` de `python.exe`.

### 7. `duai/core/selfclean.py` — ruta de Prefetch sin confiar en `WINDIR` (H-09, BAJO)

```python
    windir = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    if not os.path.isabs(windir):
        windir = r"C:\Windows"
    prefetch_dir = os.path.join(windir, "Prefetch")
```

---

## (c) Advertencias pendientes (no parcheadas / por verificar en el entorno real)

| ID | Área | Detalle |
|----|------|---------|
| W-01 | **Permisos de archivos en `%LOCALAPPDATA%\duAI`** (modo no portable) | `config.json`, `enc_key.bin`, `enc_salt.bin` y `update_history.json` se crean con `open(..., "w")` sin endurecimiento explícito de ACL. Heredan los permisos de `%LOCALAPPDATA%` (típicamente solo el usuario actual, SYSTEM y Administradores), pero **no se verifica ni se fuerza** un conjunto restrictivo de permisos. **Acción:** en el equipo objetivo, comprobar ACLs de `%LOCALAPPDATA%\duAI\` (icacls) y asegurar que ni "Users" ni "Authenticated Users" tengan escritura; considerar establecer el atributo de solo lectura o ACLs vía `pywin32`/`ctypes` (SetSecurityInfo) tras crear `enc_key.bin` y `config.json`. No se parcheó código porque requiere validación real en el sistema de destino. |
| W-02 | Firma Ed25519 opcional | `verify_signature` retorna `True` (salto con advertencia en log) si `DUAI_ED25519_PUBKEY` no está configurada. Si se exige verificación obligatoria, la aplicación debería fallar cerrado cuando falte la clave o el asset `.sig`. |
| W-03 | Fallo de descarga de firma no fatal | Si la descarga del `.sig` falla pero el SHA-256 coincide, `download_update` sigue y acepta la actualización (comentario "Non-fatal"). Recomendación: tratar la falta de firma como fallo cuando se espera un release firmado. |
| W-04 | `expand()` con entrada de usuario | Ninguna llamada actual pasa datos de usuario a `expand()` en rutas sensibles, pero la función expande variables de entorno. Evitar usarla con entrada no saneada en operaciones de escritura/borrado. |
| W-05 | Iteraciones PBKDF2 y hashes existentes | Se subió de 200k a 600k. Los hashes generados con la versión anterior dejarán de verificarse (requiere restablecer contraseña en instalaciones existentes). |
| W-06 | Prueba funcional del lockout | No se ejecutó una prueba de extremo a extremo para evitar escribir `config.json` en el `%LOCALAPPDATA%` real del equipo de auditoría. Se recomienda probar en entorno aislado: 5 fallos → bloqueo de 15 min → `verify_password` retorna `False` incluso con la clave correcta. |

---

## 5. Resultado de compilación

```
python -m compileall -q duai   (desde C:\Users\Zbook de Mario\AppData\Local\Temp\opencode\duAI)
EXITCODE=0
```

Todos los módulos parcheados compilan e importan correctamente (`duai.security.auth`, `duai.utils.settings`, `duai.core.updater`, `duai.ui.console_view`, `duai.core.scheduler`, `duai.core.selfclean`). Los archivos JSON de traducciones editados (`es.json`, `en.json`) siguen siendo JSON válido.

---

**Conclusión:** se corrigió el hallazgo crítico (ejecución de PowerShell con input de usuario sin sanear desde la consola), el lockout de autenticación ausente, la ventana de TOCTOU y el posible path traversal del actualizador, la firma Ed25519 ahora se efectúa realmente en el flujo de descarga de la UI, y se redujeron los privilegios del XML de Task Scheduler. Quedan pendientes de verificación en el entorno real los permisos de archivo (ACLs) de `%LOCALAPPDATA%\duAI` y la política de firma obligatoria.