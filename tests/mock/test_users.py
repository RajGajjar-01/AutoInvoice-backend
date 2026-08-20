import uuid
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


class TestUsers:
    def test_read_users_me(self, client: TestClient, mock_user):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        r = client.get(f"{settings.API_V1_STR}/users/me")
        assert r.status_code == 200
        assert r.json()["email"] == "user@test.com"

    def test_update_user_me(self, client: TestClient, mock_user):
        mock_user.full_name = "Updated"
        mock_svc = AsyncMock()
        mock_svc.update_me = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.patch(
            f"{settings.API_V1_STR}/users/me", json={"full_name": "Updated"}
        )
        assert r.status_code == 200

    def test_delete_user_me(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete_me = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/users/me")
        assert r.status_code == 204

    def test_delete_user_me_superuser_forbidden(
        self, client: TestClient, mock_superuser
    ):
        from app.exceptions import ForbiddenError

        mock_svc = AsyncMock()
        mock_svc.delete_me = AsyncMock(
            side_effect=ForbiddenError(
                "Super users are not allowed to delete themselves"
            )
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/users/me")
        assert r.status_code == 403

    def test_read_user_by_id(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_by_id_for_user = AsyncMock(return_value=mock_user)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/users/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_read_user_by_id_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_by_id_for_user = AsyncMock(
            side_effect=NotFoundError("User not found")
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/users/{uuid.uuid4()}")
        assert r.status_code == 404


class TestAdminUsers:
    def test_admin_list_users(self, client: TestClient, mock_superuser):
        mock_svc = AsyncMock()
        mock_svc.list_users = AsyncMock(return_value=([mock_superuser], 1))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/admin/users")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_admin_create_user(self, client: TestClient, mock_superuser):
        mock_svc = AsyncMock()
        mock_svc.create_user_as_admin = AsyncMock(return_value=mock_superuser)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/admin/users",
            json={"email": "new@test.com", "password": "testpass123"},
        )
        assert r.status_code == 201
        assert r.json()["email"] == "admin@test.com"

    def test_admin_get_user(self, client: TestClient, mock_superuser):
        mock_svc = AsyncMock()
        mock_svc.get_by_id_or_404 = AsyncMock(return_value=mock_superuser)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_admin_update_user(self, client: TestClient, mock_superuser):
        mock_svc = AsyncMock()
        mock_superuser.full_name = "Updated By Admin"
        mock_superuser.is_active = False
        mock_svc.update_user_as_admin = AsyncMock(return_value=mock_superuser)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}",
            json={"full_name": "Updated By Admin", "is_active": False},
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated By Admin"

    def test_admin_delete_user(self, client: TestClient, mock_superuser):
        mock_svc = AsyncMock()
        mock_svc.delete_user = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_admin_delete_self_forbidden(self, client: TestClient, mock_superuser):
        from app.exceptions import ForbiddenError

        mock_svc = AsyncMock()
        mock_svc.delete_user = AsyncMock(
            side_effect=ForbiddenError(
                "Super users are not allowed to delete themselves"
            )
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_superuser
        app.dependency_overrides[deps.get_current_active_superuser] = lambda: (
            mock_superuser
        )
        app.dependency_overrides[deps.get_user_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}")
        assert r.status_code == 403
