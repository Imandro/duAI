"""Actualizacion automatica de duAI desde GitHub Releases con verificacion de integridad.

Consulta la ultima version disponible, la compara con la actual y, si hay una
mas nueva, descarga el instalador / portable correspondiente.
IMPORTANTE: se verifica el hash SHA-256 del archivo descargado contra el hash
publicado en los release notes o en un archivo .sha256 adjunto, para evitar
la instalacion de binarios comprometidos (RCE).

Todo es opcional y el usuario decide si instala.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from ..i18n import t
from ..utils.logger import log
from ..utils.settings import get_settings

# Versión actual de duAI. Sube este número en cada release.
CURRENT_VERSION = "2.0.0"

GITHUB_API = "https://api.github.com/repos/Imandro/duAI/releases/latest"
RELEASES_PAGE = "https://github.com/Imandro/duAI/releases"


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
    """Extrae un hash SHA-256 (64 hex) de un texto (release notes o archivo .sha256)."""
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

    # Comparar versiones simples (semver basico)
    try:
        current_parts = [int(x) for x in CURRENT_VERSION.split(".")]
        latest_parts = [int(x) for x in result.latest_version.split(".")]
        if latest_parts > current_parts:
            result.available = True
    except ValueError:
        result.available = bool(result.latest_version) and result.latest_version != CURRENT_VERSION

    # Buscar el asset mas adecuado (preferir instalador, luego portable)
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith((".exe", ".msi")):
            result.download_url = asset.get("browser_download_url", "")
            result.asset_name = asset.get("name", "")
            # Buscar un archivo .sha256 correspondiente
            sha_name = asset.get("name", "") + ".sha256"
            for sa in assets:
                if sa.get("name", "").lower() == sha_name.lower():
                    result.sha256_url = sa.get("browser_download_url", "")
                    break
            break

    # Si no hay .sha256 adjunto, intentar extraer hash de las release notes
    if not result.sha256_url and result.release_notes:
        result.expected_sha256 = _extract_sha256_from_text(result.release_notes)

    return result


def check_for_updates_async(callback):
    """Lanza check_for_updates en un hilo y llama a callback(result) al terminar."""

    def _run():
        result = check_for_updates()
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
            callback(result)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def _compute_sha256(file_path: str) -> str:
    """Calcula el hash SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_update(url: str, dest_path: str, expected_sha256: str = "", progress_cb=None) -> bool:
    """Descarga un archivo a dest_path y, si se esperaba hash, lo verifica.

    Devuelve True solo si la descargo tuvo exito Y (si se proporciono hash) el hash coincide.
    """
    try:
        req = Request(url, headers={"User-Agent": "duAI-Updater/2.0"})
        with urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            block = 65536
            # Escribir a archivo temporal primero, luego renombrar (escritura atomica)
            tmp_path = dest_path + ".part"
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(block)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)

        # Verificar hash si se proporciono
        if expected_sha256:
            actual = _compute_sha256(tmp_path)
            if actual.lower() != expected_sha256.lower():
                log("updater", hash_mismatch=True, expected=expected_sha256, actual=actual)
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                return False

        # Escritura atomica: renombrar .part al destino final
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)
        return True
    except Exception as exc:
        log("updater", download_error=str(exc))
        try:
            if os.path.exists(dest_path + ".part"):
                os.remove(dest_path + ".part")
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
