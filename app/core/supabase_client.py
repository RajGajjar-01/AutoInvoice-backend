"""
Supabase Client Initialization Module.

This module provides initialized Supabase clients for:
- Public operations (using publishable key)
- Admin operations (using service role key)

The official supabase-py client handles:
- JWT verification
- Auth API calls
- Real-time subscriptions (if needed)
- Storage and database operations
"""

from typing import Any

from supabase import Client, create_client

from app.core.config import settings

_client: Client | None = None
_admin_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Get or create the Supabase client for public operations.

    Uses the publishable key (anon key in older terminology).
    This client can be used for:
    - Sign up / sign in
    - OAuth flows
    - Token refresh
    - Password reset requests
    - User updates (own data only)

    Returns:
        Supabase Client instance
    """
    global _client

    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_PUBLISHABLE_KEY,
        )

    return _client


def get_supabase_admin_client() -> Client:
    """
    Get or create the Supabase admin client.

    Uses the service role key with elevated privileges.
    This client can be used for:
    - Admin user management
    - Bypassing RLS policies
    - Batch operations
    - User impersonation

    WARNING: Only use this client in server-side code,
    never expose the service role key to the frontend.

    Returns:
        Supabase Client instance with admin privileges
    """
    global _admin_client

    if _admin_client is None:
        _admin_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SECRET_KEY,
        )

    return _admin_client


def reset_clients() -> None:
    """
    Reset client instances (useful for testing).
    """
    global _client, _admin_client
    _client = None
    _admin_client = None


class SupabaseAuthService:
    """
    Service class for Supabase authentication operations.

    Wraps the supabase-py auth methods with proper error handling
    and return types.
    """

    def __init__(self, use_admin: bool = False):
        self.client = (
            get_supabase_admin_client() if use_admin else get_supabase_client()
        )

    async def sign_up(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Sign up a new user.

        Args:
            email: User email
            password: User password
            full_name: Optional full name (stored in user_metadata)

        Returns:
            Dict with user and session data
        """
        options: dict[str, Any] = {}
        if full_name:
            options["data"] = {"full_name": full_name}

        response = self.client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": options,
            }
        )

        return self._response_to_dict(response)

    async def sign_in_with_password(
        self,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        """
        Sign in with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            Dict with session data
        """
        response = self.client.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        return self._response_to_dict(response)

    async def sign_out(self, access_token: str | None = None) -> None:
        """
        Sign out the current user.

        Args:
            access_token: Optional access token (uses current session if not provided)
        """
        if access_token:
            self.client.auth.admin.sign_out(access_token)
        else:
            self.client.auth.sign_out()

    async def get_session(self, access_token: str) -> dict[str, Any] | None:
        """
        Get session from access token.

        Args:
            access_token: JWT access token

        Returns:
            Session dict or None
        """
        try:
            response = self.client.auth.get_session()
            return self._response_to_dict(response)
        except Exception:
            return None

    async def get_user(self, access_token: str) -> dict[str, Any] | None:
        """
        Get user from access token.

        Args:
            access_token: JWT access token

        Returns:
            User dict or None
        """
        try:
            response = self.client.auth.get_user(access_token)
            return self._user_to_dict(response.user)
        except Exception:
            return None

    async def refresh_session(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh the session using a refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            New session data
        """
        response = self.client.auth.refresh_session(refresh_token)
        return self._response_to_dict(response)

    async def reset_password_email(self, email: str) -> None:
        """
        Send password reset email.

        Args:
            email: User email
        """
        self.client.auth.reset_password_email(email)

    async def update_user(
        self,
        access_token: str,
        password: str | None = None,
        email: str | None = None,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Update user information.

        Args:
            access_token: JWT access token
            password: New password (optional)
            email: New email (optional)
            full_name: New full name (optional)
            avatar_url: Avatar URL (optional)

        Returns:
            Updated user data
        """
        attributes: dict[str, Any] = {}

        if password:
            attributes["password"] = password
        if email:
            attributes["email"] = email

        data: dict[str, Any] = {}
        if full_name:
            data["full_name"] = full_name
        if avatar_url:
            data["avatar_url"] = avatar_url

        if data:
            attributes["data"] = data

        response = self.client.auth.update_user(attributes)
        return self._user_to_dict(response.user)

    async def resend_verification_email(self, email: str) -> None:
        """
        Resend email verification.

        Args:
            email: User email
        """
        self.client.auth.resend(
            {
                "type": "signup",
                "email": email,
            }
        )

    async def get_oauth_url(
        self,
        provider: str,
        redirect_to: str | None = None,
    ) -> str:
        """
        Get OAuth authorization URL.

        Args:
            provider: OAuth provider (google, github, apple, etc.)
            redirect_to: Redirect URL after OAuth

        Returns:
            OAuth authorization URL
        """
        options: dict[str, Any] = {}
        if redirect_to:
            options["redirect_to"] = redirect_to

        response = self.client.auth.get_oauth_url(
            provider=provider,
            options=options,
        )

        return response

    async def sign_in_with_oauth(
        self,
        provider: str,
        redirect_to: str | None = None,
    ) -> str:
        """
        Initiate OAuth sign in.

        Args:
            provider: OAuth provider
            redirect_to: Redirect URL after OAuth

        Returns:
            OAuth authorization URL
        """
        options: dict[str, Any] = {}
        if redirect_to:
            options["redirect_to"] = redirect_to

        response = self.client.auth.sign_in_with_oauth(
            {
                "provider": provider,
                "options": options,
            }
        )

        return response.url

    async def link_identity(
        self,
        access_token: str,
        provider: str,
        redirect_to: str | None = None,
    ) -> str:
        """
        Link OAuth identity to existing user.

        Args:
            access_token: User's access token
            provider: OAuth provider
            redirect_to: Redirect URL

        Returns:
            OAuth authorization URL
        """
        options: dict[str, Any] = {}
        if redirect_to:
            options["redirect_to"] = redirect_to

        response = self.client.auth.link_identity(
            {
                "provider": provider,
                "options": options,
            }
        )

        return response.url

    async def unlink_identity(
        self,
        access_token: str,
        provider: str,
        identity_id: str,
    ) -> None:
        """
        Unlink OAuth identity from user.

        Args:
            access_token: User's access token
            provider: OAuth provider
            identity_id: Identity ID to unlink
        """
        self.client.auth.unlink_identity(
            {
                "identity": {
                    "provider": provider,
                    "identity_id": identity_id,
                },
            }
        )

    async def get_user_identities(
        self,
        access_token: str,
    ) -> list[dict[str, Any]]:
        """
        Get all OAuth identities for a user.

        Args:
            access_token: User's access token

        Returns:
            List of identity dicts
        """
        response = self.client.auth.get_user(access_token)

        if response.user and response.user.identities:
            return [
                {
                    "id": identity.id,
                    "provider": identity.provider,
                    "identity_data": identity.identity_data,
                }
                for identity in response.user.identities
            ]

        return []

    async def get_sessions(self, access_token: str) -> list[dict[str, Any]]:
        """
        List all active sessions for a user (admin only).

        Args:
            access_token: User's access token

        Returns:
            List of session dicts
        """
        user_response = self.client.auth.get_user(access_token)
        if not user_response.user:
            return []

        admin_client = get_supabase_admin_client()
        response = admin_client.auth.admin.list_sessions(user_response.user.id)

        return [
            {
                "id": session.id,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "user_agent": session.user_agent,
                "ip": session.ip,
            }
            for session in response
        ]

    async def delete_session(
        self,
        session_id: str,
    ) -> None:
        """
        Delete a specific session (admin only).

        Args:
            session_id: Session ID to delete
        """
        admin_client = get_supabase_admin_client()
        admin_client.auth.admin.delete_session(session_id)

    def _response_to_dict(self, response: Any) -> dict[str, Any]:
        """Convert auth response to dictionary."""
        result: dict[str, Any] = {}

        if hasattr(response, "session") and response.session:
            result["access_token"] = response.session.access_token
            result["refresh_token"] = response.session.refresh_token
            result["expires_in"] = response.session.expires_in
            result["expires_at"] = response.session.expires_at
            result["token_type"] = response.session.token_type

        if hasattr(response, "user") and response.user:
            result["user"] = self._user_to_dict(response.user)

        return result

    def _user_to_dict(self, user: Any) -> dict[str, Any]:
        """Convert user object to dictionary."""
        return {
            "id": str(user.id) if user.id else None,
            "email": user.email,
            "email_confirmed_at": user.email_confirmed_at,
            "phone": user.phone,
            "phone_confirmed_at": user.phone_confirmed_at,
            "last_sign_in_at": user.last_sign_in_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "user_metadata": user.user_metadata or {},
            "app_metadata": user.app_metadata or {},
            "identities": [
                {
                    "id": identity.id,
                    "provider": identity.provider,
                }
                for identity in (user.identities or [])
            ]
            if user.identities
            else [],
        }


class SupabaseAdminService(SupabaseAuthService):
    """
    Admin service with elevated privileges.

    Uses the service role key for operations that require
    admin access.
    """

    def __init__(self):
        super().__init__(use_admin=True)

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        List all users (paginated).

        Args:
            page: Page number
            page_size: Items per page

        Returns:
            Dict with users list and pagination info
        """
        response = self.client.auth.admin.list_users(
            page=page,
            per_page=page_size,
        )

        users = [self._user_to_dict(user) for user in response.users]

        return {
            "users": users,
            "total": len(users),
            "page": page,
            "page_size": page_size,
        }

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user by ID.

        Args:
            user_id: Supabase user ID

        Returns:
            User dict or None
        """
        try:
            response = self.client.auth.admin.get_user_by_id(user_id)
            return self._user_to_dict(response.user)
        except Exception:
            return None

    async def create_user(
        self,
        email: str,
        password: str,
        email_confirm: bool = True,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new user (admin).

        Args:
            email: User email
            password: User password
            email_confirm: Auto-confirm email
            full_name: Optional full name

        Returns:
            Created user data
        """
        attributes: dict[str, Any] = {
            "email": email,
            "password": password,
            "email_confirm": email_confirm,
        }

        if full_name:
            attributes["user_metadata"] = {"full_name": full_name}

        response = self.client.auth.admin.create_user(attributes)
        return self._user_to_dict(response.user)

    async def update_user_by_id(
        self,
        user_id: str,
        email: str | None = None,
        password: str | None = None,
        email_confirm: bool = True,
        full_name: str | None = None,
        ban_duration: str | None = None,
    ) -> dict[str, Any]:
        """
        Update user by ID (admin).

        Args:
            user_id: Supabase user ID
            email: New email
            password: New password
            email_confirm: Confirm email change
            full_name: New full name
            ban_duration: Ban duration (e.g., "24h")

        Returns:
            Updated user data
        """
        attributes: dict[str, Any] = {}

        if email:
            attributes["email"] = email
            attributes["email_confirm"] = email_confirm
        if password:
            attributes["password"] = password
        if ban_duration:
            attributes["ban_duration"] = ban_duration

        user_metadata: dict[str, Any] = {}
        if full_name:
            user_metadata["full_name"] = full_name

        if user_metadata:
            attributes["user_metadata"] = user_metadata

        response = self.client.auth.admin.update_user_by_id(user_id, attributes)
        return self._user_to_dict(response.user)

    async def delete_user(self, user_id: str) -> None:
        """
        Delete user by ID.

        Args:
            user_id: Supabase user ID
        """
        self.client.auth.admin.delete_user(user_id)


auth_service = SupabaseAuthService()
admin_auth_service = SupabaseAdminService()
