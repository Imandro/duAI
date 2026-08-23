import hashlib
import hmac
import secrets

from ..utils.settings import get_settings

_ITERATIONS = 200_000


def _derive(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ITERATIONS
    ).hex()


def set_password(password):
    store = get_settings()
    salt = secrets.token_hex(16)
    store.set("password_salt", salt)
    store.set("password_hash", _derive(password, salt))


def verify_password(password):
    store = get_settings()
    salt = store.get("password_salt")
    stored_hash = store.get("password_hash")
    if not salt or not stored_hash:
        return True
    return hmac.compare_digest(_derive(password, salt), stored_hash)


def has_password():
    store = get_settings()
    return bool(store.get("password_hash"))


def clear_password():
    store = get_settings()
    store.set("password_hash", None)
    store.set("password_salt", None)
