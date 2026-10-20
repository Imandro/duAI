"""Gestión de configuración para duAI - Validación, encriptación, migración, backup."""

import json
import os
import re
import threading
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .logger import base_dir, log


@dataclass
class ConfigField:
    """Definición de esquema para un campo de configuración."""
    type: type
    default: Any
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    sensitive: bool = False  # Marcar para encriptación


CONFIG_SCHEMA: Dict[str, ConfigField] = {
    "exclusions": ConfigField(list, [], lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v), "Rutas excluidas"),
    "password_hash": ConfigField(str, None, lambda v: v is None or (isinstance(v, str) and len(v) >= 32), "Hash Argon2", sensitive=True),
    "password_salt": ConfigField(str, None, lambda v: v is None or (isinstance(v, str) and len(v) == 32), "Salt para hash", sensitive=True),
    "auto_clean_on_exit": ConfigField(bool, False, None, "Limpiar al salir"),
    "auto_interval_min": ConfigField(int, 0, lambda v: isinstance(v, int) and v >= 0, "Intervalo auto-limpieza (min)"),
    "hotkey_enabled": ConfigField(bool, False, None, "Hotkey global habilitado"),
    "hotkey_requires_confirm": ConfigField(bool, True, None, "Confirmar hotkey pánico"),
    "panic_mode": ConfigField(str, "recycle", lambda v: v in ("recycle", "shred", "hide"), "Modo pánico"),
    "self_purge_on_exit": ConfigField(bool, False, None, "Purgar datos app al salir"),
    "hosts_block": ConfigField(bool, False, None, "Bloquear via hosts"),
    "ui_mode": ConfigField(str, "dark", lambda v: v in ("dark", "dark_hc", "light", "light_hc"), "Tema UI"),
    "high_contrast": ConfigField(bool, False, None, "Alto contraste"),
    "follow_system_theme": ConfigField(bool, True, None, "Seguir tema del sistema"),
    "language": ConfigField(str, "es", lambda v: isinstance(v, str) and len(v) == 2, "Código idioma ISO"),
    "float_visible": ConfigField(bool, False, None, "Widget flotante visible"),
    "float_x": ConfigField(int, None, lambda v: v is None or (isinstance(v, int) and v >= 0), "Posición X flotante"),
    "float_y": ConfigField(int, None, lambda v: v is None or (isinstance(v, int) and v >= 0), "Posición Y flotante"),
    "float_size": ConfigField(int, 160, lambda v: isinstance(v, int) and 80 <= v <= 400, "Tamaño flotante"),
    "check_updates": ConfigField(bool, True, None, "Verificar actualizaciones"),
    "accent_color": ConfigField(str, "", lambda v: v == "" or re.match(r"^#[0-9a-fA-F]{6}$", v), "Color acento hex"),
    "gamification": ConfigField(bool, True, None, "Logros habilitados"),
    "share_platform": ConfigField(str, "twitter", lambda v: v in ("twitter", "mastodon", "linkedin", "copy"), "Plataforma compartir"),
    "portable_mode": ConfigField(bool, False, None, "Modo portable"),
}

CONFIG_VERSION = 4  # Incrementar al cambiar esquema


# Migraciones registradas
MIGRATIONS: Dict[int, Callable[[dict], dict]] = {}


def register_migration(from_version: int):
    """Decorador para registrar función de migración."""
    def decorator(func: Callable[[dict], dict]):
        MIGRATIONS[from_version] = func
        return func
    return decorator


@register_migration(1)
def migrate_v1_to_v2(data: dict) -> dict:
    """Migración v1 -> v2: renombrar claves, añadir defaults."""
    migrated = dict(data)
    if "old_exclusions" in migrated:
        migrated["exclusions"] = migrated.pop("old_exclusions")
    migrated.setdefault("panic_mode", "recycle")
    return migrated


@register_migration(2)
def migrate_v2_to_v3(data: dict) -> dict:
    """Migración v2 -> v3: añadir campos gamificación."""
    migrated = dict(data)
    migrated.setdefault("gamification", True)
    migrated.setdefault("share_platform", "twitter")
    migrated.setdefault("accent_color", "")
    return migrated


@register_migration(3)
def migrate_v3_to_v4(data: dict) -> dict:
    """Migración v3 -> v4: soporte temas light/high-contrast."""
    migrated = dict(data)
    # Migrar ui_mode antiguo
    if migrated.get("ui_mode") == "oscuro":
        migrated["ui_mode"] = "dark"
    elif migrated.get("ui_mode") == "claro":
        migrated["ui_mode"] = "light"
    migrated.setdefault("high_contrast", False)
    migrated.setdefault("follow_system_theme", True)
    migrated.setdefault("hotkey_requires_confirm", True)
    return migrated


# Encriptación
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    Fernet = None


_LOCK = threading.Lock()
_INSTANCE = None


class SettingsStore:
    """Almacén de configuración con validación, encriptación, migración y backup."""

    _ENCRYPTION_SALT_FILE = "enc_salt.bin"
    _ENCRYPTION_KEY_FILE = "enc_key.bin"
    _BACKUP_DIR = "backups"
    _MAX_BACKUPS = 10

    def __init__(self):
        self._path = os.path.join(base_dir(), "config.json")
        self._data = {}
        self._fernet = None
        self._save_timer = None
        self._pending_save = False
        self._init_encryption()
        self._load()

    def _init_encryption(self):
        """Inicializa o carga clave de encriptación derivada de entropía máquina/usuario."""
        if not HAS_CRYPTOGRAPHY:
            return

        salt_path = os.path.join(base_dir(), self._ENCRYPTION_SALT_FILE)
        key_path = os.path.join(base_dir(), self._ENCRYPTION_KEY_FILE)

        if os.path.exists(key_path) and os.path.exists(salt_path):
            with open(salt_path, "rb") as f:
                salt = f.read()
            with open(key_path, "rb") as f:
                key = f.read()
        else:
            salt = secrets.token_bytes(16)
            machine_id = self._get_machine_entropy()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100_000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_id))

            with open(salt_path, "wb") as f:
                f.write(salt)
            with open(key_path, "wb") as f:
                f.write(key)

        self._fernet = Fernet(key)

    def _get_machine_entropy(self) -> bytes:
        """Obtiene entropía específica de la máquina para derivación de clave."""
        import platform
        import uuid
        parts = [
            platform.node().encode(),
            platform.machine().encode(),
            str(uuid.getnode()).encode(),
            os.getenv("USERNAME", "").encode(),
        ]
        return hashlib.sha256(b"".join(parts)).digest()

    def _encrypt(self, value: str) -> str:
        """Encripta un valor string."""
        if value is None or not self._fernet:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        """Desencripta un valor string."""
        if value is None or not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except Exception:
            log("config_decrypt_failed", key="unknown")
            return None

    def _validate(self, key: str, value: Any) -> bool:
        field = CONFIG_SCHEMA.get(key)
        if not field:
            return False
        if not isinstance(value, field.type):
            return False
        if field.validator and not field.validator(value):
            return False
        return True

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)

            # Manejar migración
            stored_version = stored.get("_config_version", 1)
            if stored_version < CONFIG_VERSION:
                stored = self._migrate(stored, stored_version)

            # Validar y aplicar
            for key, field in CONFIG_SCHEMA.items():
                value = stored.get(key, field.default)
                if field.sensitive and value is not None:
                    value = self._decrypt(value)
                if self._validate(key, value):
                    self._data[key] = value
                else:
                    self._data[key] = field.default
                    log("config_validation_failed", key=key, value=str(value), expected=field.type.__name__)

        except (OSError, ValueError) as e:
            log("config_load_failed", error=str(e))
            self._data = {k: v.default for k, v in CONFIG_SCHEMA.items()}

    def _migrate(self, stored: dict, from_version: int) -> dict:
        """Aplica todas las migraciones secuencialmente."""
        migrated = dict(stored)
        for version in range(from_version, CONFIG_VERSION):
            migrator = MIGRATIONS.get(version)
            if migrator:
                try:
                    migrated = migrator(migrated)
                    log("config_migration_step", from_version=version, to_version=version + 1)
                except Exception as e:
                    log("config_migration_failed", from_version=version, error=str(e))
                    for key, field in CONFIG_SCHEMA.items():
                        migrated.setdefault(key, field.default)
                    break
        migrated["_config_version"] = CONFIG_VERSION
        return migrated

    def _get_backup_dir(self) -> str:
        path = os.path.join(base_dir(), self._BACKUP_DIR)
        os.makedirs(path, exist_ok=True)
        return path

    def _schedule_save(self, delay: float = 0.5):
        """Debounce saves - espera a que cesen cambios rápidos."""
        if self._save_timer:
            self._save_timer.cancel()
        self._pending_save = True
        self._save_timer = threading.Timer(delay, self._flush_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _flush_save(self):
        with _LOCK:
            if not self._pending_save:
                return
            self._pending_save = False
        self.save()

    def save(self):
        """Guarda configuración en disco (escritura atómica)."""
        with _LOCK:
            try:
                to_save = dict(self._data)
                for key, field in CONFIG_SCHEMA.items():
                    if field.sensitive and to_save.get(key) is not None:
                        to_save[key] = self._encrypt(to_save[key])

                to_save["_config_version"] = CONFIG_VERSION

                temp_path = self._path + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as fh:
                    json.dump(to_save, fh, indent=2)
                os.replace(temp_path, self._path)
            except OSError as e:
                log("config_save_failed", error=str(e))

    def force_save(self):
        """Guarda inmediatamente (ej. al salir de la app)."""
        if self._save_timer:
            self._save_timer.cancel()
        self._flush_save()

    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Establece valor con validación. Returns True si válido y guardado."""
        if key not in CONFIG_SCHEMA:
            log("config_unknown_key", key=key)
            return False

        if not self._validate(key, value):
            log("config_invalid_value", key=key, value=str(value))
            return False

        with _LOCK:
            self._data[key] = value

        self._schedule_save()
        return True

    def get_all(self) -> dict:
        return dict(self._data)

    # ===== BACKUP / RESTORE =====

    def create_backup(self, label: str = "manual") -> str:
        """Crea backup timestamped de la config actual."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"config_{label}_{timestamp}.json"
        backup_path = os.path.join(self._get_backup_dir(), backup_name)

        to_backup = dict(self._data)
        for key, field in CONFIG_SCHEMA.items():
            if field.sensitive and to_backup.get(key) is not None:
                to_backup[key] = self._encrypt(to_backup[key])
        to_backup["_config_version"] = CONFIG_VERSION
        to_backup["_backup_label"] = label
        to_backup["_backup_time"] = timestamp

        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(to_backup, f, indent=2)
            self._prune_backups()
            log("config_backup_created", path=backup_path)
            return backup_path
        except OSError as e:
            log("config_backup_failed", error=str(e))
            return ""

    def _prune_backups(self):
        """Mantiene solo los N backups más recientes."""
        from pathlib import Path
        backup_dir = Path(self._get_backup_dir())
        backups = sorted(backup_dir.glob("config_*.json"), key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-self._MAX_BACKUPS]:
            try:
                old_backup.unlink()
            except OSError:
                pass

    def list_backups(self) -> List[dict]:
        """Lista backups disponibles con metadatos."""
        from pathlib import Path
        backups = []
        for path in Path(self._get_backup_dir()).glob("config_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                backups.append({
                    "path": str(path),
                    "label": data.get("_backup_label", "unknown"),
                    "time": data.get("_backup_time", ""),
                    "version": data.get("_config_version", 1),
                })
            except (OSError, ValueError):
                pass
        return sorted(backups, key=lambda b: b["time"], reverse=True)

    def restore_backup(self, backup_path: str) -> bool:
        """Restaura config desde un archivo de backup."""
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            if "_config_version" not in backup_data:
                log("config_restore_invalid", path=backup_path)
                return False

            # Backup de la config actual antes de restaurar
            self.create_backup("pre_restore")

            self._data = {}
            self._load_from_dict(backup_data)
            self.save()

            log("config_restored", from_backup=backup_path)
            return True
        except (OSError, ValueError) as e:
            log("config_restore_failed", path=backup_path, error=str(e))
            return False

    def _load_from_dict(self, data: dict):
        """Carga config desde diccionario (usado por restore)."""
        stored_version = data.get("_config_version", 1)
        if stored_version < CONFIG_VERSION:
            data = self._migrate(data, stored_version)

        for key, field in CONFIG_SCHEMA.items():
            value = data.get(key, field.default)
            if field.sensitive and value is not None:
                value = self._decrypt(value)
            if self._validate(key, value):
                self._data[key] = value
            else:
                self._data[key] = field.default


def get_settings() -> SettingsStore:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SettingsStore()
    return _INSTANCE


def set_portable_mode(enabled: bool):
    """Establece modo portable (redirige base_dir)."""
    # Esto se maneja en logger.py
    pass