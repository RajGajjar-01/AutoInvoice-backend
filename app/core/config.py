import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
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
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_HOST: str = ""
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    PORT: int = 8000

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str = "AutoInvoice"
    SENTRY_DSN: str | None = None

    # Support Railway's DATABASE_URL directly
    DATABASE_URL: str | None = None

    POSTGRES_SERVER: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.SQLALCHEMY_DATABASE_URI

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Prefer DATABASE_URL if set (Railway provides this)
        if self.DATABASE_URL:
            # Convert postgres:// to postgresql+psycopg:// for async
            db_url = self.DATABASE_URL
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return db_url

        # Otherwise construct from individual vars
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    # Brevo (transactional/system emails: password reset, new account, test email)
    BREVO_API_KEY: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    # Google OAuth (Gmail send-as-user: sending invoices from the user's own inbox)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/google/callback"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    OPENWA_BASE_URL: str = "http://localhost:2785"
    OPENWA_API_KEY: str = ""
    OPENWA_SESSION_ID: str = ""

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.BREVO_API_KEY and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "changethis"

    @model_validator(mode="after")
    def _enforce_secrets(self) -> Self:
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in environment")
        if self.SECRET_KEY == "changethis":
            raise ValueError(
                'SECRET_KEY is still set to "changethis", please change it'
            )
        if self.POSTGRES_PASSWORD and self.POSTGRES_PASSWORD == "changethis":
            raise ValueError(
                'POSTGRES_PASSWORD is still set to "changethis", please change it'
            )
        if (
            self.FIRST_SUPERUSER_PASSWORD
            and self.FIRST_SUPERUSER_PASSWORD == "changethis"
        ):
            raise ValueError(
                'FIRST_SUPERUSER_PASSWORD is still set to "changethis", please change it'
            )
        return self

    @model_validator(mode="after")
    def _validate_production_config(self) -> Self:
        if self.ENVIRONMENT == "production":
            has_db_url = bool(self.DATABASE_URL)
            has_db_creds = bool(
                self.POSTGRES_SERVER
                and self.POSTGRES_USER
                and self.POSTGRES_PASSWORD
                and self.POSTGRES_DB
            )
            if not has_db_url and not has_db_creds:
                raise ValueError(
                    "Production requires either DATABASE_URL or all of: "
                    "POSTGRES_SERVER, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB"
                )
            if not self.FRONTEND_HOST:
                raise ValueError("FRONTEND_HOST is required in production")
        return self


settings = Settings()  # type: ignore
