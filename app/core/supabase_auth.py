"""
Supabase Authentication Module.

This module provides JWT verification using JWKS for asymmetric
token validation. It uses the official supabase-py client for
auth API operations.

Key features:
- JWKS-based JWT verification (ES256/RS256)
- Caches JWKS for performance
- Token extraction from headers
- User ID extraction from verified tokens
"""

import time
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError

from app.core.config import settings
from app.exceptions import InvalidTokenError, TokenExpiredError

SUPABASE_AUTH_URL = f"{settings.SUPABASE_URL}/auth/v1"


class JWKSManager:
    """
    Manages JWKS (JSON Web Key Set) fetching and caching.

    Supabase exposes public keys at:
    https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
    """

    _jwks_client: PyJWKClient | None = None
    _jwks_cache_time: float = 0
    _cache_ttl: int = 3600

    @classmethod
    def get_jwks_client(cls) -> PyJWKClient:
        """
        Get or create a JWKS client with caching.

        The client caches keys internally, but we also refresh
        periodically to handle key rotation.
        """
        current_time = time.time()

        if (
            cls._jwks_client is None
            or (current_time - cls._jwks_cache_time) > cls._cache_ttl
        ):
            cls._jwks_client = PyJWKClient(
                settings.SUPABASE_JWKS_URL,
                cache_keys=True,
            )
            cls._jwks_cache_time = current_time

        return cls._jwks_client

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the JWKS cache (useful for testing or forced refresh)."""
        cls._jwks_client = None
        cls._jwks_cache_time = 0


def get_signing_key(token: str) -> tuple[str, str]:
    """
    Extract the signing key from a JWT token using JWKS.

    Args:
        token: The JWT token string

    Returns:
        Tuple of (signing_key, key_id)

    Raises:
        InvalidTokenError: If the token is invalid or key not found
    """
    try:
        jwks_client = JWKSManager.get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid", "unknown")
        return signing_key.key, kid
    except JWTInvalidTokenError as e:
        raise InvalidTokenError(f"Failed to get signing key: {str(e)}")


def verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verify a Supabase JWT token using JWKS.

    This is the main entry point for token verification.
    It uses asymmetric key verification (ES256) via the JWKS endpoint.

    Args:
        token: The JWT token string (without "Bearer " prefix)

    Returns:
        The decoded token payload containing user claims:
        - sub: User UUID
        - email: User email
        - role: User role (usually "authenticated")
        - aud: Audience
        - iss: Issuer
        - exp: Expiration timestamp
        - iat: Issued at timestamp
        - session_id: Supabase session ID

    Raises:
        InvalidTokenError: If token verification fails
        TokenExpiredError: If token has expired
    """
    try:
        signing_key, kid = get_signing_key(token)

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            options={
                "verify_aud": False,
                "verify_iss": True,
            },
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
        )

        if "sub" not in payload:
            raise InvalidTokenError("Token missing 'sub' claim (user ID)")

        return payload

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTInvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")


def extract_user_id(token: str) -> str:
    """
    Extract the user ID (sub claim) from a verified token.

    Args:
        token: The JWT token string

    Returns:
        The user UUID string

    Raises:
        InvalidTokenError: If token is invalid
    """
    payload = verify_supabase_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise InvalidTokenError("Token does not contain a user ID")

    return user_id


def extract_email(token: str) -> str | None:
    """
    Extract the email from a verified token.

    Args:
        token: The JWT token string

    Returns:
        The user email or None
    """
    payload = verify_supabase_token(token)
    return payload.get("email")


def get_token_from_header(authorization_header: str | None) -> str:
    """
    Extract the token from an Authorization header.

    Args:
        authorization_header: The Authorization header value

    Returns:
        The token string (without "Bearer " prefix)

    Raises:
        InvalidTokenError: If header is missing or malformed
    """
    if not authorization_header:
        raise InvalidTokenError("Authorization header is missing")

    if not authorization_header.startswith("Bearer "):
        raise InvalidTokenError("Authorization header must use Bearer scheme")

    return authorization_header[7:]


async def get_current_user_id(authorization: str | None) -> str:
    """
    Async function to get the current user ID from an Authorization header.

    This is designed to be used in FastAPI dependencies.

    Args:
        authorization: The Authorization header value

    Returns:
        The user UUID string

    Raises:
        InvalidTokenError: If token verification fails
    """
    token = get_token_from_header(authorization)
    return extract_user_id(token)


def is_email_verified(payload: dict[str, Any]) -> bool:
    """
    Check if email is verified from JWT payload.

    Args:
        payload: The decoded JWT payload

    Returns:
        True if email is verified
    """
    return bool(payload.get("email_verified", False))


def get_user_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Get user metadata from JWT payload.

    Args:
        payload: The decoded JWT payload

    Returns:
        User metadata dict
    """
    return payload.get("user_metadata", {}) or {}
