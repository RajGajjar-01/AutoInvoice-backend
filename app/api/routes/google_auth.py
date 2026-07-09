import logging
import uuid
from datetime import timedelta

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from jwt.exceptions import InvalidTokenError

from app.api.deps import CurrentUser, UserServiceDep
from app.core import security
from app.core.config import settings
from app.core.time import get_datetime_utc
from app.schemas import GoogleAuthUrl, GoogleStatus, Message
from app.services import google_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google", tags=["google"])

STATE_TOKEN_TYPE = "google_oauth_state"
STATE_TOKEN_EXPIRE_MINUTES = 10


def _create_state_token(user_id: uuid.UUID) -> str:
    expire = get_datetime_utc() + timedelta(minutes=STATE_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": STATE_TOKEN_TYPE, "exp": expire},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def _decode_state_token(state: str) -> uuid.UUID:
    payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
    if payload.get("type") != STATE_TOKEN_TYPE:
        raise InvalidTokenError("Invalid state token type")
    return uuid.UUID(payload["sub"])


@router.get("/connect", response_model=GoogleAuthUrl)
def connect_google(current_user: CurrentUser) -> GoogleAuthUrl:
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=503, detail="Google sign-in is not configured on this server"
        )
    state = _create_state_token(current_user.id)
    return GoogleAuthUrl(url=google_oauth_service.get_authorization_url(state))


@router.get("/status", response_model=GoogleStatus)
def google_status(current_user: CurrentUser) -> GoogleStatus:
    return GoogleStatus(
        connected=current_user.google_connected,
        email=current_user.google_email,
    )


@router.get("/callback")
async def google_callback(
    user_service: UserServiceDep,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    settings_url = f"{settings.FRONTEND_HOST}/settings"

    if error or not code or not state:
        return RedirectResponse(f"{settings_url}?google=error")

    try:
        user_id = _decode_state_token(state)
    except (InvalidTokenError, ValueError):
        return RedirectResponse(f"{settings_url}?google=error")

    user = await user_service.get_by_id(user_id)
    if not user:
        return RedirectResponse(f"{settings_url}?google=error")

    try:
        tokens = google_oauth_service.exchange_code_for_tokens(code)
        google_email = google_oauth_service.get_user_email(tokens["access_token"])
    except httpx.HTTPError:
        logger.exception("Google OAuth token exchange failed")
        return RedirectResponse(f"{settings_url}?google=error")

    await user_service.save_google_tokens(
        user,
        email=google_email,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in", 3600),
    )
    return RedirectResponse(f"{settings_url}?google=connected")


@router.post("/disconnect", response_model=Message)
async def disconnect_google(
    current_user: CurrentUser, user_service: UserServiceDep
) -> Message:
    await user_service.disconnect_google(current_user)
    return Message(message="Google account disconnected")
