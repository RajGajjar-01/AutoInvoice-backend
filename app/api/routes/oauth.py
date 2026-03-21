from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlmodel import SQLModel

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.supabase_client import auth_service
from app.exceptions import parse_supabase_error
from app.models import AuthIdentity, Message

router = APIRouter(tags=["oauth"])

SUPPORTED_OAUTH_PROVIDERS = [
    "google",
    "github",
    "apple",
    "discord",
    "twitter",
    "facebook",
    "microsoft",
    "azure",
    "bitbucket",
    "figma",
    "fly",
    "gitlab",
    "kakao",
    "keycloak",
    "linkedin",
    "linkedin_oidc",
    "notion",
    "slack",
    "spotify",
    "twitch",
    "workos",
]


class OAuthURLResponse(SQLModel):
    url: str
    provider: str


@router.get("/auth/oauth/{provider}")
async def get_oauth_url(
    provider: str,
    redirect_to: str | None = Query(None, description="URL to redirect after OAuth"),
) -> OAuthURLResponse:
    """
    Get OAuth authorization URL for a provider.

    Frontend should redirect user to this URL to start OAuth flow.

    Supported providers: google, github, apple, discord, twitter, facebook,
    microsoft, azure, bitbucket, figma, fly, gitlab, kakao, keycloak,
    linkedin, linkedin_oidc, notion, slack, spotify, twitch, workos
    """
    if provider.lower() not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OAuth provider. Supported: {', '.join(SUPPORTED_OAUTH_PROVIDERS)}",
        )

    try:
        url = await auth_service.sign_in_with_oauth(
            provider=provider.lower(),
            redirect_to=redirect_to,
        )
        return OAuthURLResponse(url=url, provider=provider.lower())
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.get("/auth/oauth/callback")
async def oauth_callback(
    code: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """
    Handle OAuth callback from providers.

    This endpoint is called by Supabase after OAuth authentication.
    In most cases, the frontend handles the callback directly.

    The frontend receives the tokens and calls /auth/me to get user info.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=error_description or error,
        )

    frontend_url = f"{settings.FRONTEND_HOST}/auth/callback"
    if code:
        frontend_url += f"?code={code}"

    return RedirectResponse(url=frontend_url)


@router.post("/auth/oauth/link/{provider}")
async def link_oauth_provider(
    provider: str,
    current_user: CurrentUser,
    authorization: str | None = Header(None),
    redirect_to: str | None = Query(None),
) -> OAuthURLResponse:
    """
    Link an OAuth provider to the current user account.

    Requires valid access token in Authorization header.
    """
    if provider.lower() not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OAuth provider. Supported: {', '.join(SUPPORTED_OAUTH_PROVIDERS)}",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    token = authorization[7:]

    try:
        url = await auth_service.link_identity(
            access_token=token,
            provider=provider.lower(),
            redirect_to=redirect_to,
        )
        return OAuthURLResponse(url=url, provider=provider.lower())
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.delete("/auth/oauth/{provider}")
async def unlink_oauth_provider(
    provider: str,
    identity_id: str,
    current_user: CurrentUser,
    authorization: str | None = Header(None),
) -> Message:
    """
    Unlink an OAuth provider from the current user account.

    Requires:
    - Valid access token in Authorization header
    - The identity_id to unlink (get from /auth/oauth/identities)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    token = authorization[7:]

    try:
        await auth_service.unlink_identity(
            access_token=token,
            provider=provider.lower(),
            identity_id=identity_id,
        )
        return Message(message=f"Successfully unlinked {provider}")
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.get("/auth/oauth/identities", response_model=list[AuthIdentity])
async def get_oauth_identities(
    current_user: CurrentUser,
    authorization: str | None = Header(None),
) -> list[AuthIdentity]:
    """
    Get all OAuth identities linked to the current user.

    Returns list of providers the user has linked.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    token = authorization[7:]

    try:
        identities = await auth_service.get_user_identities(access_token=token)
        return [
            AuthIdentity(
                id=identity.get("id", ""),
                provider=identity.get("provider", ""),
                identity_data=identity.get("identity_data"),
            )
            for identity in identities
        ]
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )
