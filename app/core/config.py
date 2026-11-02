import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_HOST: str = "http://localhost:5173"
    # Secure by default: an unset ENVIRONMENT is treated as production, which
    # enforces non-default secrets, Secure cookies, disables the unauthenticated
    # /private routes and hides the interactive API docs. Set ENVIRONMENT=local
    # explicitly for development.
    ENVIRONMENT: Literal["local", "staging", "production"] = "production"

    # Extra origins (besides the CORS origins) allowed to send cookie-authenticated
    # state-changing requests, e.g. the API's own origin if a UI is served from it.
    CSRF_TRUSTED_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    # Brute-force / enumeration protection for authentication endpoints.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 900
    LOGIN_MAX_FAILED_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_PER_IP: int = 100
    SIGNUP_RATE_LIMIT_PER_IP: int = 20
    PASSWORD_RECOVERY_RATE_LIMIT_PER_IP: int = 10
    PASSWORD_RECOVERY_RATE_LIMIT_PER_EMAIL: int = 3
    RESET_PASSWORD_RATE_LIMIT_PER_IP: int = 20

    # Maximum page size accepted by list endpoints.
    MAX_PAGE_SIZE: int = 100

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST.rstrip("/")
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def csrf_trusted_origins(self) -> list[str]:
        return self.all_cors_origins + [
            str(origin).rstrip("/") for origin in self.CSRF_TRUSTED_ORIGINS
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    def _fail_or_warn(self, message: str) -> None:
        if self.ENVIRONMENT == "local":
            warnings.warn(message, stacklevel=1)
        else:
            raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )
        if len(self.SECRET_KEY) < 32:
            self._fail_or_warn(
                "SECRET_KEY must be at least 32 characters; generate one with "
                '`python -c "import secrets; print(secrets.token_urlsafe(32))"`.'
            )
        if "*" in self.all_cors_origins:
            # Starlette reflects the request Origin for credentialed requests when
            # "*" is configured, which would let any site make authenticated calls.
            self._fail_or_warn(
                "BACKEND_CORS_ORIGINS must not contain '*' because credentials "
                "(cookies) are allowed; list explicit origins instead."
            )
        return self


settings = Settings()  # type: ignore
