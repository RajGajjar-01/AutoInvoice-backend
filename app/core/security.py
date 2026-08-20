import base64
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import jwt
from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings

password_hash = PasswordHash((Argon2Hasher(),))

ALGORITHM = "HS256"


@lru_cache
def _get_master_encryption_key() -> bytes:
    if settings.ENCRYPTION_KEY:
        try:
            key = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
            if len(key) == 32:
                return key
        except Exception:
            pass
        return hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"autoinvoice-master-encryption-key",
    )
    return hkdf.derive(settings.SECRET_KEY.encode("utf-8"))


def _get_all_master_keys() -> list[bytes]:
    keys = [_get_master_encryption_key()]
    fallbacks = settings.ENCRYPTION_KEY_FALLBACKS
    if isinstance(fallbacks, str):
        fallback_list = [f.strip() for f in fallbacks.split(",") if f.strip()]
    else:
        fallback_list = list(fallbacks)
    for fb in fallback_list:
        try:
            raw = base64.urlsafe_b64decode(fb)
            if len(raw) == 32:
                keys.append(raw)
            else:
                keys.append(hashlib.sha256(fb.encode("utf-8")).digest())
        except Exception:
            keys.append(hashlib.sha256(fb.encode("utf-8")).digest())
    return keys


def derive_tenant_key(owner_id: uuid.UUID | str, master_key: bytes | None = None) -> bytes:
    if master_key is None:
        master_key = _get_master_encryption_key()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"tenant:{owner_id}".encode("utf-8"),
    )
    return hkdf.derive(master_key)


def encrypt_field(owner_id: uuid.UUID | str, plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    if plaintext == "":
        return ""
    key = derive_tenant_key(owner_id)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return "v1:" + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(owner_id: uuid.UUID | str, ciphertext_str: str | None) -> str | None:
    if ciphertext_str is None:
        return None
    if ciphertext_str == "":
        return ""

    if ciphertext_str.startswith("v1:"):
        payload = base64.urlsafe_b64decode(ciphertext_str[3:].encode("ascii"))
        nonce = payload[:12]
        ct = payload[12:]
        for master_k in _get_all_master_keys():
            try:
                t_key = derive_tenant_key(owner_id, master_k)
                aesgcm = AESGCM(t_key)
                return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
            except (InvalidTag, ValueError):
                continue
        raise ValueError("Failed to decrypt field with available encryption keys")

    # Legacy Fernet fallback
    if ciphertext_str.startswith("gAAAAA"):
        for master_k in _get_all_master_keys():
            try:
                fernet_key = base64.urlsafe_b64encode(master_k)
                f = Fernet(fernet_key)
                return f.decrypt(ciphertext_str.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError):
                continue
        # Also try legacy SECRET_KEY sha256 derivation
        try:
            legacy_key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
            f = Fernet(base64.urlsafe_b64encode(legacy_key))
            return f.decrypt(ciphertext_str.encode("ascii")).decode("utf-8")
        except Exception:
            pass

    return ciphertext_str


def mask_account_number(account: str | None) -> str | None:
    if not account:
        return account
    if len(account) <= 4:
        return "*" * len(account)
    return ("*" * (len(account) - 4)) + account[-4:]


@lru_cache
def _token_cipher() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _token_cipher().encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    return _token_cipher().decrypt(token.encode()).decode()


def create_access_token(
    subject: str | Any, expires_delta: timedelta | None = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str | Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
