"""Hash PIN Ghost (scrypt, stdlib) dan pembatas percobaan salah per klien (A-05)."""
import base64
import hashlib
import hmac
import os
import time

DEFAULT_GHOST_PIN = "03697"
_SCRYPT_PREFIX = "scrypt$"
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
MAX_PIN_FAILURES = 5
LOCKOUT_SECONDS = 300

# klien -> (jumlah gagal, waktu gagal terakhir)
_failures: dict[str, tuple[int, float]] = {}


def _scrypt(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    return _SCRYPT_PREFIX + base64.b64encode(salt).decode() + "$" + base64.b64encode(_scrypt(pin, salt)).decode()


def is_hashed(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_SCRYPT_PREFIX)


def verify_pin(stored: str | None, given: str | None) -> bool:
    """Bandingkan constant-time. `stored` boleh hash scrypt atau PIN plaintext lama (belum dimigrasi)."""
    given = given or ""
    stored = stored or DEFAULT_GHOST_PIN
    if is_hashed(stored):
        try:
            _, salt_b64, digest_b64 = stored.split("$", 2)
            expected = base64.b64decode(digest_b64)
            return hmac.compare_digest(_scrypt(given, base64.b64decode(salt_b64)), expected)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(stored.encode("utf-8"), given.encode("utf-8"))


def seconds_locked(client: str) -> int:
    count, last = _failures.get(client, (0, 0.0))
    if count < MAX_PIN_FAILURES:
        return 0
    remaining = int(last + LOCKOUT_SECONDS - time.time())
    if remaining <= 0:
        _failures.pop(client, None)
        return 0
    return remaining


def record_failure(client: str) -> None:
    count, _ = _failures.get(client, (0, 0.0))
    _failures[client] = (count + 1, time.time())


def clear_failures(client: str) -> None:
    _failures.pop(client, None)
