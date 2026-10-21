"""Actualizacion automatica de duAI desde GitHub Releases con verificacion de integridad, firmas Ed25519 y rollback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from ..i18n import t
from ..utils.logger import log
from ..utils.settings import get_settings
from ..utils.logger import base_dir

# Versión actual de duAI. Sube este número en cada release.
CURRENT_VERSION = "2.0.0"

GITHUB_API = "https://api.github.com/repos/Imandro/duAI/releases/latest"
RELEASES_PAGE = "https://github.com/Imandro/duAI/releases"

# Ed25519 public key for signature verification (base64 encoded)
# Generate with: python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; k=Ed25519PrivateKey.generate(); print(k.public_key().public_bytes_raw().hex())"
ED25519_PUBLIC_KEY = os.environ.get("DUAI_ED25519_PUBKEY", "")


class UpdateResult:
    """Resultado de una comprobacion de actualizacion."""

    def __init__(self):
        self.available = False
        self.latest_version = ""
        self.current_version = CURRENT_VERSION
        self.download_url = ""
        self.sha256_url = ""
        self.expected_sha256 = ""
        self.release_notes = ""
        self.error = ""
        self.asset_name = ""
        self.verified = False
        self.signature_url = ""


def _fetch_json(url: str, timeout: int = 15) -> dict | None:
    """Descarga un JSON de una URL con cabeceras de usuario."""
    try:
        req = Request(url, headers={"User-Agent": "duAI-Updater/2.0", "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))
    except (URLError, HTTPError, OSError, ValueError) as exc:
        log("updater", error=str(exc))
        return None


def _fetch_text(url: str, timeout: int = 15) -> str | None:
    """Descarga texto plano de una URL."""
    try:
        req = Request(url, headers={"User-Agent": "duAI-Updater/2.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (URLError, HTTPError, OSError, ValueError) as exc:
        log("updater", fetch_error=str(exc))
        return None


def _extract_sha256_from_text(text: str) -> str | None:
    """Extrae un hash SHA-256 (64 hex) de un texto."""
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if match:
        return match.group(1).lower()
    return None


def check_for_updates() -> UpdateResult:
    """Comprueba si hay una version mas nueva en GitHub. Bloqueante."""
    result = UpdateResult()
    data = _fetch_json(GITHUB_API)
    if not data:
        result.error = "No se pudo contactar con GitHub."
        return result

    tag = data.get("tag_name", "")
    if tag:
        result.latest_version = tag.lstrip("v")
    result.release_notes = data.get("body", "") or ""

    # Comparar versiones
    try:
        current_parts = [int(x) for x in CURRENT_VERSION.split(".")]
        latest_parts = [int(x) for x in result.latest_version.split(".")]
        if latest_parts > current_parts:
            result.available = True
    except ValueError:
        result.available = bool(result.latest_version) and result.latest_version != CURRENT_VERSION

    # Buscar el asset mas adecuado
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith((".exe", ".msi")):
            result.download_url = asset.get("browser_download_url", "")
            result.asset_name = asset.get("name", "")
            # Buscar archivo .sha256
            sha_name = asset.get("name", "") + ".sha256"
            for sa in assets:
                if sa.get("name", "").lower() == sha_name.lower():
                    result.sha256_url = sa.get("browser_download_url", "")
                    break
            # Buscar archivo .sig (Ed25519 signature)
            sig_name = asset.get("name", "") + ".sig"
            for sa in assets:
                if sa.get("name", "").lower() == sig_name.lower():
                    result.signature_url = sa.get("browser_download_url", "")
                    break
            break

    # Extraer hash de release notes si no hay .sha256
    if not result.sha256_url and result.release_notes:
        result.expected_sha256 = _extract_sha256_from_text(result.release_notes)

    return result


# Hilos de comprobacion pendientes (para poder esperarlos al salir)
_async_checkers: "list[threading.Thread]" = []


def check_for_updates_async(callback):
    """Lanza check_for_updates en un hilo y llama a callback(result) al terminar."""

    def _run():
        try:
            result = check_for_updates()
        except Exception as exc:  # nunca dejar el hilo morir sin avisar
            result = UpdateResult()
            result.error = str(exc)
        try:
            from PySide6.QtCore import QMetaObject, Qt, QObject

            class _Invoker(QObject):
                def __init__(self, cb, res):
                    super().__init__()
                    self._cb = cb
                    self._res = res

                def invoke(self):
                    self._cb(self._res)

            invoker = _Invoker(callback, result)
            QMetaObject.invokeMethod(
                invoker, "invoke", Qt.ConnectionType.QueuedConnection
            )
        except Exception:
            try:
                callback(result)
            except Exception:
                pass

    thread = threading.Thread(target=_run, daemon=True)
    _async_checkers.append(thread)
    thread.start()
    return thread


def join_update_checkers(timeout: float = 3.0) -> bool:
    """Espera (breve) a los hilos de comprobacion de actualizaciones.

    Evita que un hilo de red siga dentro de OpenSSL mientras Python hace el
    teardown, algo que provoca un crash del proceso al salir.
    """
    deadline = time.time() + timeout
    ok = True
    for thread in list(_async_checkers):
        remaining = max(0.1, deadline - time.time())
        thread.join(remaining)
        if thread.is_alive():
            ok = False
    _async_checkers.clear()
    return ok


def _compute_sha256(file_path: str) -> str:
    """Calcula el hash SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Alias publico (usado por la UI para verificar la descarga)
compute_sha256 = _compute_sha256


def verify_signature(file_path: str, signature_path: str) -> bool:
    """Verifica firma Ed25519 del archivo."""
    if not ED25519_PUBLIC_KEY:
        log("updater", warning="No Ed25519 public key configured, skipping signature verification")
        return True  # Skip if no key configured
    
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ED25519_PUBLIC_KEY))
        
        with open(signature_path, "rb") as f:
            signature = f.read()
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        public_key.verify(signature, data)
        log("updater", signature_verified=True)
        return True
    except InvalidSignature:
        log("updater", signature_invalid=True)
        return False
    except Exception as e:
        log("updater", signature_error=str(e))
        return False


def download_update(url: str, dest_path: str, expected_sha256: str = "", progress_cb=None, signature_url: str = "") -> bool:
    """Descarga un archivo y verifica SHA-256 y opcionalmente firma Ed25519."""
    try:
        # Saneamiento de destino: impedir path traversal a traves de dest_path.
        # Solo se permite un nombre de archivo directo dentro del directorio indicado.
        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        dest_path = os.path.join(dest_dir, os.path.basename(dest_path))
        tmp_path = dest_path + ".part"
        sig_path = dest_path + ".sig"
        req = Request(url, headers={"User-Agent": "duAI-Updater/2.0"})
        with urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            block = 65536
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(block)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)

        # Verify SHA-256
        if expected_sha256:
            actual = _compute_sha256(tmp_path)
            if actual.lower() != expected_sha256.lower():
                log("updater", hash_mismatch=True, expected=expected_sha256, actual=actual)
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                return False

        # Verify Ed25519 signature if available
        if signature_url:
            # Download signature
            try:
                sig_req = Request(signature_url, headers={"User-Agent": "duAI-Updater/2.0"})
                with urlopen(sig_req, timeout=10) as sig_resp:
                    with open(sig_path, "wb") as f:
                        f.write(sig_resp.read())
                
                if not verify_signature(tmp_path, sig_path):
                    log("updater", signature_verification_failed=True)
                    try:
                        os.remove(tmp_path)
                        os.remove(sig_path)
                    except OSError:
                        pass
                    return False
            except Exception as e:
                log("updater", signature_download_error=str(e))
                # Non-fatal if signature download fails but hash passed
            finally:
                if os.path.exists(sig_path):
                    try:
                        os.remove(sig_path)
                    except OSError:
                        pass

        # Renombre atomico: os.replace reemplaza el destino existente de forma
        # atomica tanto en Windows como en POSIX, sin ventana de TOCTOU entre
        # borrar y renombrar.
        os.replace(tmp_path, dest_path)
        return True
    except Exception as exc:
        log("updater", download_error=str(exc))
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def fetch_expected_sha256(sha256_url: str) -> str | None:
    """Descarga el contenido de un archivo .sha256 y extrae el hash."""
    if not sha256_url:
        return None
    text = _fetch_text(sha256_url)
    if text:
        return _extract_sha256_from_text(text)
    return None


def should_check_on_startup() -> bool:
    """Indica si se debe comprobar actualizaciones al arrancar."""
    return bool(get_settings().get("check_updates", True))


def set_check_on_startup(value: bool):
    get_settings().set("check_updates", bool(value))


# ==================== Update History & Rollback ====================

HISTORY_FILE = os.path.join(base_dir(), "update_history.json")
MAX_HISTORY_ENTRIES = 50


def _load_history() -> list:
    """Load update history from file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(history: list):
    """Save update history to file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-MAX_HISTORY_ENTRIES:], f, indent=2)
    except Exception:
        pass


def get_update_history() -> list:
    """Get update history."""
    return _load_history()


def add_update_history(entry: dict):
    """Add entry to update history."""
    history = _load_history()
    entry["timestamp"] = time.time()
    entry["date"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["timestamp"]))
    history.append(entry)
    _save_history(history)


def clear_update_history():
    """Clear update history."""
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except Exception:
            pass


class RollbackManager:
    """Manages rollback backups for updates."""
    
    def __init__(self, backup_dir: str = None):
        self.backup_dir = backup_dir or os.path.join(base_dir(), "rollback")
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self) -> str:
        """Create a backup of current installation for rollback."""
        timestamp = int(time.time())
        backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        
        # Backup executable and key files
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
            try:
                shutil.copy2(exe_path, os.path.join(backup_path, "duAI.exe"))
            except Exception:
                pass
        
        # Backup settings and data
        data_dir = base_dir()
        for item in ["settings.json", "stats.json"]:
            src = os.path.join(data_dir, item)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, os.path.join(backup_path, item))
                except Exception:
                    pass
        
        return backup_path
    
    def rollback_to(self, backup_path: str) -> bool:
        """Rollback to a previous backup."""
        if not os.path.exists(backup_path):
            return False
        
        try:
            # Restore executable
            if getattr(sys, "frozen", False):
                exe_backup = os.path.join(backup_path, "duAI.exe")
                if os.path.exists(exe_backup):
                    shutil.copy2(exe_backup, sys.executable)
            
            # Restore settings/data
            data_dir = base_dir()
            for item in ["settings.json", "stats.json"]:
                src = os.path.join(backup_path, item)
                dst = os.path.join(data_dir, item)
                if os.path.exists(src):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            
            return True
        except Exception:
            return False
    
    def list_backups(self) -> list:
        """List available rollback backups."""
        backups = []
        try:
            for item in os.listdir(self.backup_dir):
                path = os.path.join(self.backup_dir, item)
                if os.path.isdir(path) and item.startswith("backup_"):
                    stat = os.stat(path)
                    backups.append({
                        "path": path,
                        "timestamp": stat.st_mtime,
                        "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    })
        except Exception:
            pass
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def cleanup_old_backups(self, keep: int = 5):
        """Remove old backups, keeping only the most recent N."""
        backups = self.list_backups()
        for backup in backups[keep:]:
            try:
                shutil.rmtree(backup["path"], ignore_errors=True)
            except Exception:
                pass