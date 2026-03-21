"""
Custom exceptions for authentication and authorization errors.

These exceptions are used throughout the application to provide
clear error messages and codes for frontend consumption.
"""

from typing import Any


class AuthError(Exception):
    """
    Base exception for authentication errors.

    All auth-related exceptions inherit from this class for
    consistent error handling in exception handlers.
    """

    def __init__(
        self,
        message: str,
        code: str = "auth_error",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


class InvalidCredentialsError(AuthError):
    """Raised when email or password is incorrect."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, code="invalid_credentials")


class UserNotFoundError(AuthError):
    """Raised when a user is not found."""

    def __init__(self, message: str = "User not found"):
        super().__init__(message, code="user_not_found")


class UserAlreadyExistsError(AuthError):
    """Raised when trying to create a user that already exists."""

    def __init__(self, message: str = "User already exists", email: str | None = None):
        details = {"email": email} if email else {}
        super().__init__(message, code="user_already_exists", details=details)


class EmailNotVerifiedError(AuthError):
    """Raised when an unverified user tries to access protected resources."""

    def __init__(self, message: str = "Email not verified"):
        super().__init__(message, code="email_not_verified")


class TokenExpiredError(AuthError):
    """Raised when a token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, code="token_expired")


class InvalidTokenError(AuthError):
    """Raised when a token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, code="invalid_token")


class SessionExpiredError(AuthError):
    """Raised when a session has expired."""

    def __init__(self, message: str = "Session has expired"):
        super().__init__(message, code="session_expired")


class OAuthError(AuthError):
    """Raised when an OAuth operation fails."""

    def __init__(
        self,
        message: str = "OAuth authentication failed",
        provider: str | None = None,
    ):
        details = {"provider": provider} if provider else {}
        super().__init__(message, code="oauth_error", details=details)


class MFAError(AuthError):
    """Raised when an MFA operation fails."""

    def __init__(self, message: str = "MFA verification failed"):
        super().__init__(message, code="mfa_error")


class MFARequiredError(AuthError):
    """Raised when MFA is required but not provided."""

    def __init__(self, message: str = "MFA verification required"):
        super().__init__(message, code="mfa_required")


class PasswordResetError(AuthError):
    """Raised when a password reset operation fails."""

    def __init__(self, message: str = "Password reset failed"):
        super().__init__(message, code="password_reset_error")


class WeakPasswordError(AuthError):
    """Raised when a password does not meet requirements."""

    def __init__(self, message: str = "Password is too weak"):
        super().__init__(message, code="weak_password")


class IdentityAlreadyLinkedError(AuthError):
    """Raised when trying to link an already linked identity."""

    def __init__(
        self,
        message: str = "Identity already linked",
        provider: str | None = None,
    ):
        details = {"provider": provider} if provider else {}
        super().__init__(message, code="identity_already_linked", details=details)


class NoIdentityFoundError(AuthError):
    """Raised when an identity is not found."""

    def __init__(self, message: str = "No identity found"):
        super().__init__(message, code="no_identity_found")


class AdminOperationError(AuthError):
    """Raised when an admin operation fails."""

    def __init__(self, message: str = "Admin operation failed"):
        super().__init__(message, code="admin_operation_error")


class UnauthorizedError(AuthError):
    """Raised when a user lacks permissions."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="unauthorized")


class UserBannedError(AuthError):
    """Raised when a banned user tries to authenticate."""

    def __init__(self, message: str = "User account is banned"):
        super().__init__(message, code="user_banned")


class RateLimitError(AuthError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, code="rate_limit_exceeded")


def parse_supabase_error(error: Exception) -> AuthError:
    """
    Parse a Supabase error into an AuthError.

    Maps Supabase error messages to our custom exceptions
    for consistent error handling.
    """
    error_str = str(error).lower()

    if "invalid login credentials" in error_str:
        return InvalidCredentialsError()

    if "user already registered" in error_str:
        return UserAlreadyExistsError()

    if "email not confirmed" in error_str:
        return EmailNotVerifiedError()

    if "jwt expired" in error_str or "token expired" in error_str:
        return TokenExpiredError()

    if "invalid jwt" in error_str or "invalid token" in error_str:
        return InvalidTokenError()

    if "session not found" in error_str:
        return SessionExpiredError()

    if "user banned" in error_str:
        return UserBannedError()

    if "rate limit" in error_str:
        return RateLimitError()

    if "password" in error_str and ("weak" in error_str or "short" in error_str):
        return WeakPasswordError()

    if "identity" in error_str and "already" in error_str:
        return IdentityAlreadyLinkedError()

    return AuthError(
        message=str(error),
        code="supabase_error",
        details={"original_error": str(error)},
    )
