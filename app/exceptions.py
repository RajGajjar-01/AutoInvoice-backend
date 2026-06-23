from typing import Any


class AuthError(Exception):
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
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, code="invalid_credentials")


class UserNotFoundError(AuthError):
    def __init__(self, message: str = "User not found"):
        super().__init__(message, code="user_not_found")


class UserAlreadyExistsError(AuthError):
    def __init__(self, message: str = "User already exists", email: str | None = None):
        details = {"email": email} if email else {}
        super().__init__(message, code="user_already_exists", details=details)


class EmailNotVerifiedError(AuthError):
    def __init__(self, message: str = "Email not verified"):
        super().__init__(message, code="email_not_verified")


class TokenExpiredError(AuthError):
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, code="token_expired")


class InvalidTokenError(AuthError):
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, code="invalid_token")


class SessionExpiredError(AuthError):
    def __init__(self, message: str = "Session has expired"):
        super().__init__(message, code="session_expired")


class UnauthorizedError(AuthError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="unauthorized")


class UserBannedError(AuthError):
    def __init__(self, message: str = "User account is banned"):
        super().__init__(message, code="user_banned")


class RateLimitError(AuthError):
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, code="rate_limit_exceeded")


class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "Not enough permissions"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str = "Conflict"):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str = "Invalid request"):
        self.message = message
        super().__init__(message)
