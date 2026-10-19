"""Actualizacion automatica de duAI desde GitHub Releases.

Consulta la ultima version disponible, la compara con la actual y, si hay una
mas nueva, descarga el instalador / portable correspondiente. Todo es opcional
y el usuario decide si instala.
"""

from __future__ import annotations

import json
import os
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
        self.release_notes = ""
        self.error = ""
        self.asset_name = ""


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
            break

    return result


def check_for_updates_async(callback):
    """Lanza check_for_updates en un hilo y llama a callback(result) al terminar."""

    def _run():
        result = check_for_updates()
        # Ejecutar callback en el hilo principal si es posible (Qt)
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


def download_update(url: str, dest_path: str, progress_cb=None) -> bool:
    """Descarga un archivo a dest_path. Devuelve True si tuvo exito."""
    try:
        req = Request(url, headers={"User-Agent": "duAI-Updater/2.0"})
        with urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            block = 8192
            with open(dest_path, "wb") as out:
                while True:
                    chunk = resp.read(block)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        return True
    except Exception as exc:
        log("updater", download_error=str(exc))
        return False


def should_check_on_startup() -> bool:
    """Indica si se debe comprobar actualizaciones al arrancar."""
    return bool(get_settings().get("check_updates", True))


def set_check_on_startup(value: bool):
    get_settings().set("check_updates", bool(value))
