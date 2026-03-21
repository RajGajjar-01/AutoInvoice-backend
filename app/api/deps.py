import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session

from app import crud
from app.core.db import engine
from app.core.supabase_auth import (
    get_user_metadata,
    is_email_verified,
    verify_supabase_token,
)
from app.models import Profile


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_token_from_auth_header(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )
    return authorization[7:]


TokenDep = Annotated[str, Depends(get_token_from_auth_header)]


def get_current_user(session: SessionDep, token: TokenDep) -> Profile:
    """
    Get the current user from a Supabase JWT token.

    Uses JWKS verification for asymmetric JWT validation.
    The token is verified using Supabase's public keys.

    If user doesn't exist in local profiles table, creates one from JWT claims.
    """
    try:
        payload = verify_supabase_token(token)
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token: missing user ID",
            )

        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user ID format",
            )

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Could not validate credentials: {str(e)}",
        )

    profile = crud.get_profile_by_id(session=session, user_id=user_uuid)

    if not profile:
        user_metadata = get_user_metadata(payload)
        profile = Profile(
            id=user_uuid,
            email=email or f"{user_id}@supabase",
            full_name=user_metadata.get("full_name"),
            avatar_url=user_metadata.get("avatar_url"),
            is_verified=is_email_verified(payload),
            is_superuser=False,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
    else:
        needs_update = False
        if profile.is_verified != is_email_verified(payload):
            profile.is_verified = is_email_verified(payload)
            needs_update = True
        if profile.email != email:
            profile.email = email
            needs_update = True

        user_metadata = get_user_metadata(payload)
        if user_metadata.get("full_name") and profile.full_name != user_metadata.get(
            "full_name"
        ):
            profile.full_name = user_metadata.get("full_name")
            needs_update = True
        if user_metadata.get("avatar_url") and profile.avatar_url != user_metadata.get(
            "avatar_url"
        ):
            profile.avatar_url = user_metadata.get("avatar_url")
            needs_update = True

        if needs_update:
            session.add(profile)
            session.commit()
            session.refresh(profile)

    return profile


CurrentUser = Annotated[Profile, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> Profile:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


SuperUserDep = Annotated[Profile, Depends(get_current_active_superuser)]
