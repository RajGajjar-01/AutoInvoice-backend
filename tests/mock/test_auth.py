import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _mock_user(overrides=None):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "user@test.com"
    u.is_active = True
    u.is_superuser = False
    u.hashed_password = "$argon2id$hash"
    u.full_name = "Test User"
    u.is_verified = True
    u.avatar_url = None
    u.created_at = MagicMock()
    u.updated_at = MagicMock()
    if overrides:
        for k, v in overrides.items():
            setattr(u, k, v)
    return u


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


class TestSignup:
    def test_signup_success(self, client: TestClient, monkeypatch):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["signup"])
        mock_service.signup = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        monkeypatch.setattr("app.api.routes.auth.security.create_access_token", lambda **kw: "access")
        monkeypatch.setattr("app.api.routes.auth.security.create_refresh_token", lambda **kw: "refresh")

        r = client.post(
            f"{settings.API_V1_STR}/auth/signup",
            json={"email": "new@test.com", "password": "testpass123", "full_name": "New"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["access_token"] == "access"
        assert data["user"]["email"] == "user@test.com"

    def test_signup_existing(self, client: TestClient):
        from app.exceptions import ConflictError
        mock_service = AsyncMock(spec=["signup"])
        mock_service.signup = AsyncMock(side_effect=ConflictError("A user with this email already exists"))
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        r = client.post(
            f"{settings.API_V1_STR}/auth/signup",
            json={"email": "existing@test.com", "password": "testpass123"},
        )
        assert r.status_code == 400

    def test_signup_short_password(self, client: TestClient):
        r = client.post(
            f"{settings.API_V1_STR}/auth/signup",
            json={"email": "new@test.com", "password": "short"},
        )
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client: TestClient, monkeypatch):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["authenticate"])
        mock_service.authenticate = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        monkeypatch.setattr("app.api.routes.auth.security.create_access_token", lambda **kw: "access")
        monkeypatch.setattr("app.api.routes.auth.security.create_refresh_token", lambda **kw: "refresh")

        r = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": "user@test.com", "password": "testpass123"},
        )
        assert r.status_code == 200
        assert r.json()["access_token"] == "access"

    def test_login_invalid(self, client: TestClient):
        mock_service = AsyncMock(spec=["authenticate"])
        mock_service.authenticate = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        r = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": "user@test.com", "password": "wrong"},
        )
        assert r.status_code == 400


class TestRefresh:
    def test_refresh_success(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.api.routes.auth.jwt.decode", lambda *a, **kw: {"type": "refresh", "sub": str(uuid.uuid4())})

        from sqlmodel.ext.asyncio.session import AsyncSession
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=_mock_user())

        async def override_db():
            yield mock_session
        app.dependency_overrides[deps.get_db] = override_db

        monkeypatch.setattr("app.api.routes.auth.security.create_access_token", lambda **kw: "new_access")
        monkeypatch.setattr("app.api.routes.auth.security.create_refresh_token", lambda **kw: "new_refresh")

        client.cookies.set("refresh_token", "valid_refresh")
        r = client.post(f"{settings.API_V1_STR}/auth/refresh")
        assert r.status_code == 200
        assert r.json()["access_token"] == "new_access"

    def test_refresh_no_token(self, client: TestClient):
        r = client.post(f"{settings.API_V1_STR}/auth/refresh")
        assert r.status_code == 401

    def test_refresh_invalid_token(self, client: TestClient, monkeypatch):
        def bad_decode(*a, **kw):
            from jwt.exceptions import InvalidTokenError
            raise InvalidTokenError()
        monkeypatch.setattr("app.api.routes.auth.jwt.decode", bad_decode)

        client.cookies.set("refresh_token", "invalid")
        r = client.post(f"{settings.API_V1_STR}/auth/refresh")
        assert r.status_code == 401


class TestForgotPassword:
    def test_forgot_password(self, client: TestClient, monkeypatch):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["get_by_email"])
        mock_service.get_by_email = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        monkeypatch.setattr("app.api.routes.auth.generate_password_reset_token", lambda email: "reset_tok")
        monkeypatch.setattr("app.api.routes.auth.generate_reset_password_email", lambda **kw: MagicMock(subject="reset", html_content="<html>"))
        monkeypatch.setattr("app.api.routes.auth.send_email", lambda **kw: None)

        r = client.post(f"{settings.API_V1_STR}/auth/forgot-password", params={"email": "user@test.com"})
        assert r.status_code == 200


class TestResetPassword:
    def test_reset_success(self, client: TestClient, monkeypatch):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["get_by_email", "update_password"])
        mock_service.get_by_email = AsyncMock(return_value=mock_user)
        mock_service.update_password = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service

        monkeypatch.setattr("app.api.routes.auth.verify_password_reset_token", lambda token: "user@test.com")

        r = client.post(
            f"{settings.API_V1_STR}/auth/reset-password",
            json={"token": "valid", "new_password": "newpass1234"},
        )
        assert r.status_code == 200

    def test_reset_invalid_token(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.api.routes.auth.verify_password_reset_token", lambda token: None)
        r = client.post(
            f"{settings.API_V1_STR}/auth/reset-password",
            json={"token": "bad", "new_password": "newpass1234"},
        )
        assert r.status_code == 400


class TestUpdatePassword:
    def test_update_success(self, client: TestClient, monkeypatch):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["authenticate", "update_password"])
        mock_service.authenticate = AsyncMock(return_value=mock_user)
        mock_service.update_password = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user

        r = client.post(
            f"{settings.API_V1_STR}/auth/update-password",
            json={"current_password": "oldpass123", "new_password": "newpass1234"},
        )
        assert r.status_code == 200

    def test_update_wrong_current(self, client: TestClient):
        mock_user = _mock_user()
        mock_service = AsyncMock(spec=["authenticate"])
        mock_service.authenticate = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_service
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user

        r = client.post(
            f"{settings.API_V1_STR}/auth/update-password",
            json={"current_password": "wrongpass", "new_password": "newpass1234"},
        )
        assert r.status_code == 400


class TestAuthMe:
    def test_get_me(self, client: TestClient):
        test_user = _mock_user()
        app.dependency_overrides[deps.get_current_user] = lambda: test_user

        r = client.get(f"{settings.API_V1_STR}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "user@test.com"
