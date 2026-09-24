import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt

from app.core import security
from app.core.config import settings
from app.core.time import get_datetime_utc

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = " ".join(
    [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/gmail.send",
    ]
)

STATE_TOKEN_TYPE = "google_oauth_state"
STATE_TOKEN_EXPIRE_MINUTES = 10

OAuthMode = Literal["login", "connect"]


def get_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_BASE_URL}?{urlencode(params)}"


def create_state_token(
    *, user_id: uuid.UUID | None, mode: OAuthMode, nonce: str | None = None
) -> str:
    expire = get_datetime_utc() + timedelta(minutes=STATE_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "type": STATE_TOKEN_TYPE,
        "mode": mode,
        "exp": expire,
    }
    if user_id is not None:
        payload["sub"] = str(user_id)
    if nonce is not None:
        payload["nonce"] = nonce
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=security.ALGORITHM)


@dataclass(frozen=True)
class OAuthState:
    mode: OAuthMode
    user_id: uuid.UUID | None
    nonce: str | None


def decode_state_token(state: str) -> OAuthState:
    payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
    if payload.get("type") != STATE_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Invalid state token type")
    sub = payload.get("sub")
    return OAuthState(
        mode=payload.get("mode", "connect"),
        user_id=uuid.UUID(sub) if sub else None,
        nonce=payload.get("nonce"),
    )


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


@dataclass(frozen=True)
class GoogleUserInfo:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


def get_user_info(access_token: str) -> GoogleUserInfo:
    response = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return GoogleUserInfo(
        sub=str(data["id"]),
        email=str(data["email"]),
        email_verified=bool(data.get("verified_email", False)),
        name=data.get("name"),
        picture=data.get("picture"),
    )
