import hashlib
import hmac
import secrets
import time

from ..utils.settings import get_settings

# PBKDF2-HMAC-SHA256. 600k iteraciones segun recomendaciones actuales (OWASP 2023).
# Nota: los hashes generados con versiones anteriores (200k) dejaran de ser validos.
_ITERATIONS = 600_000
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60  # bloqueo de 15 minutos tras 5 fallos consecutivos


def _derive(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ITERATIONS
    ).hex()


def _now() -> float:
    return time.time()


def set_password(password):
    store = get_settings()
    salt = secrets.token_hex(16)
    store.set("password_salt", salt)
    store.set("password_hash", _derive(password, salt))
    store.set("password_fail_count", 0)
    store.set("password_lock_until", None)


def verify_password(password):
    store = get_settings()
    salt = store.get("password_salt")
    stored_hash = store.get("password_hash")
    if not salt or not stored_hash:
        return True

    # Respeto de bloqueo por intentos fallidos
    lock_until = store.get("password_lock_until")
    if lock_until:
        try:
            if _now() < float(lock_until):
                return False  # cuenta bloqueada temporalmente
        except (TypeError, ValueError):
            pass
        # Bloqueo expirado: se reanuda con contador limpio
        store.set("password_fail_count", 0)
        store.set("password_lock_until", None)

    ok = hmac.compare_digest(_derive(password, salt), stored_hash)
    if ok:
        store.set("password_fail_count", 0)
        store.set("password_lock_until", None)
    else:
        fails = int(store.get("password_fail_count") or 0) + 1
        store.set("password_fail_count", fails)
        if fails >= _MAX_FAILED_ATTEMPTS:
            store.set("password_lock_until", str(_now() + _LOCKOUT_SECONDS))
    return ok


def has_password():
    store = get_settings()
    return bool(store.get("password_hash"))


def clear_password():
    store = get_settings()
    store.set("password_hash", None)
    store.set("password_salt", None)
