"""Tests for authentication endpoints."""

import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Profile
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def test_get_access_token(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        user_id = str(uuid.uuid4())
        mock_auth.sign_in_with_password = AsyncMock(
            return_value={
                "access_token": "test-token",
                "refresh_token": "test-refresh",
                "expires_in": 3600,
                "user": {
                    "id": user_id,
                    "email": settings.FIRST_SUPERUSER,
                    "email_confirmed_at": "2024-01-01T00:00:00Z",
                },
            }
        )

        r = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={
                "email": settings.FIRST_SUPERUSER,
                "password": settings.FIRST_SUPERUSER_PASSWORD,
            },
        )
        tokens = r.json()
        assert r.status_code == 200
        assert "access_token" in tokens
        assert tokens["access_token"] == "test-token"


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        from app.exceptions import InvalidCredentialsError

        mock_auth.sign_in_with_password = AsyncMock(
            side_effect=Exception("Invalid credentials")
        )

        r = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": settings.FIRST_SUPERUSER, "password": "incorrect"},
        )
        assert r.status_code == 400


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch("app.api.deps.verify_supabase_token") as mock_verify:
        user_id = str(uuid.uuid4())
        mock_verify.return_value = {
            "sub": user_id,
            "email": settings.FIRST_SUPERUSER,
            "email_verified": True,
        }

        r = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers=superuser_token_headers,
        )
        result = r.json()
        assert r.status_code == 200
        assert "email" in result


def test_signup(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        user_id = str(uuid.uuid4())
        mock_auth.sign_up = AsyncMock(
            return_value={
                "access_token": "test-token",
                "refresh_token": "test-refresh",
                "expires_in": 3600,
                "user": {
                    "id": user_id,
                    "email": "newuser@example.com",
                },
            }
        )

        r = client.post(
            f"{settings.API_V1_STR}/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert r.status_code == 200
        result = r.json()
        assert "access_token" in result


def test_refresh_token(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        mock_auth.refresh_session = AsyncMock(
            return_value={
                "access_token": "new-test-token",
                "refresh_token": "new-test-refresh",
                "expires_in": 3600,
            }
        )

        r = client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            json={"refresh_token": "old-refresh-token"},
        )
        assert r.status_code == 200
        result = r.json()
        assert result["access_token"] == "new-test-token"


def test_forgot_password(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        mock_auth.reset_password_email = AsyncMock(return_value=None)

        r = client.post(
            f"{settings.API_V1_STR}/auth/forgot-password",
            json={"email": "test@example.com"},
        )
        assert r.status_code == 200
        assert "message" in r.json()


def test_logout(client: TestClient) -> None:
    with patch("app.api.routes.auth.auth_service") as mock_auth:
        mock_auth.sign_out = AsyncMock(return_value=None)

        r = client.post(
            f"{settings.API_V1_STR}/auth/logout",
            headers={"Authorization": "Bearer test-token"},
        )
        assert r.status_code == 200
        assert "message" in r.json()
