import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"

# Every JWT this service issues carries a "type" claim so that a token minted for
# one purpose can never be accepted for another (e.g. an access token used as a
# refresh token, or a password-reset token used as a session).
TokenType = Literal["access", "refresh", "password_reset"]
TOKEN_TYPE_ACCESS: TokenType = "access"
TOKEN_TYPE_REFRESH: TokenType = "refresh"
TOKEN_TYPE_PASSWORD_RESET: TokenType = "password_reset"

_REQUIRED_CLAIMS = ["exp", "iat", "sub", "type"]


def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {
        **claims,
        "iat": now,
        "nbf": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing signature, expiry and token type.

    Raises ``jwt.InvalidTokenError`` on any failure.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": _REQUIRED_CLAIMS},
    )
    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type")
    return payload


def create_access_token(
    subject: str | Any, expires_delta: timedelta, token_version: int = 0
) -> str:
    return _encode(
        {"sub": str(subject), "type": TOKEN_TYPE_ACCESS, "ver": token_version},
        expires_delta,
    )


def create_refresh_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    token_version: int = 0,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode(
        {"sub": str(subject), "type": TOKEN_TYPE_REFRESH, "ver": token_version},
        expires_delta,
    )


def password_fingerprint(hashed_password: str) -> str:
    """Keyed fingerprint of the stored password hash.

    Embedding this in a password-reset token makes the token single-use: once the
    password changes, the stored hash (and therefore the fingerprint) changes and
    every outstanding reset token for that account stops validating. The HMAC key
    prevents the fingerprint from leaking anything about the hash itself.
    """
    return hmac.new(
        settings.SECRET_KEY.encode(), hashed_password.encode(), hashlib.sha256
    ).hexdigest()[:32]


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
