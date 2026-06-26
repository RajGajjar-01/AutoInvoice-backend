import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


class TestUtils:
    def test_health_check(self, client: TestClient):
        r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
        assert r.status_code == 200
        assert r.json() is True

    def test_test_email(self, client: TestClient, mock_superuser, monkeypatch):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: mock_superuser

        monkeypatch.setattr("app.api.routes.utils.generate_test_email", lambda **kw: MagicMock(subject="Test", html_content="<html>"))
        monkeypatch.setattr("app.api.routes.utils.send_email", lambda **kw: None)

        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/",
            params={"email_to": "test@example.com"},
        )
        assert r.status_code == 201
        assert r.json()["message"] == "Test email sent"


class TestPrivate:
    def test_create_user_private(self, client: TestClient):
        mock_svc = AsyncMock()
        new_user = MagicMock()
        new_user.id = uuid.uuid4()
        new_user.email = "private@test.com"
        new_user.is_active = True
        new_user.is_superuser = False
        new_user.full_name = "Private User"
        new_user.is_verified = True
        new_user.avatar_url = None
        new_user.created_at = None
        new_user.updated_at = None
        mock_svc.create_user_private = AsyncMock(return_value=new_user)
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json={"email": "private@test.com", "password": "testpass123", "full_name": "Private User"},
        )
        assert r.status_code == 201
        assert r.json()["email"] == "private@test.com"


class TestExceptions:
    def test_forgot_password(self, client: TestClient):
        r = client.post(f"{settings.API_V1_STR}/auth/logout")
        assert r.status_code == 200

    def test_sentry_debug(self, client: TestClient):
        try:
            client.get("/sentry-debug")
        except ZeroDivisionError:
            pass

    def test_root_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"
