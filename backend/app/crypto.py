from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from .config import SECRET_KEY_PATH

_fernet = None


def _load_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = b""
    if SECRET_KEY_PATH.exists():
        key = SECRET_KEY_PATH.read_bytes().strip()
    if not key:
        key = Fernet.generate_key()
        SECRET_KEY_PATH.write_bytes(key)
        try:
            os.chmod(SECRET_KEY_PATH, 0o600)
        except OSError:
            pass

    _fernet = Fernet(key)
    return _fernet


def encrypt(plain: str) -> str:
    return _load_fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _load_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
