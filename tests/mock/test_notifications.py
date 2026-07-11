import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _notif(overrides=None):
    n = MagicMock()
    n.id = uuid.uuid4()
    n.owner_id = uuid.uuid4()
    n.type = "info"
    n.title = "Test"
    n.description = None
    n.read = False
    n.table_id = None
    n.table_name = None
    n.row_id = None
    n.row_label = None
    n.scheduled_for = None
    n.created_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(n, k, v)
    return n


class TestNotifications:
    def test_list_notifications(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([], 0, 0))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/notifications/")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_list_with_filters(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([], 0, 0))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/notifications/?unread_only=true&type=reminder")
        assert r.status_code == 200

    def test_create_notification(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_notif())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/notifications/",
            json={"type": "info", "title": "Test Notification"},
        )
        assert r.status_code == 201
        assert r.json()["title"] == "Test"

    def test_get_notification(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(return_value=_notif())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_get_notification_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(side_effect=NotFoundError("Notification not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_update_notification(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_notif({"read": True}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.patch(f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}", json={"read": True})
        assert r.status_code == 200
        assert r.json()["read"] is True

    def test_delete_notification(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_mark_all_read(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.mark_all_read = AsyncMock(return_value=3)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.post(f"{settings.API_V1_STR}/notifications/mark-all-read")
        assert r.status_code == 200
        assert "3" in r.json()["message"]

    def test_clear_all(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.clear_all = AsyncMock(return_value=5)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_notification_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/notifications/")
        assert r.status_code == 204


def _settings(overrides=None):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.owner_id = uuid.uuid4()
    s.name = "My Company"
    s.gstin = None
    s.pan = None
    s.address = None
    s.city = None
    s.state = None
    s.pincode = None
    s.phone = None
    s.email = None
    s.website = None
    s.logo_url = None
    s.signature_url = None
    s.bank_name = None
    s.bank_account = None
    s.bank_ifsc = None
    s.bank_branch = None
    s.upi_id = None
    s.terms_and_conditions = None
    s.invoice_prefix = "INV-"
    s.quotation_prefix = "QUO-"
    s.proforma_prefix = "PRO-"
    s.challan_prefix = "CHL-"
    s.whatsapp_enabled = False
    s.openwa_base_url = "http://localhost:2785"
    s.openwa_api_key = None
    s.openwa_session_id = None
    s.smtp_host = None
    s.smtp_port = 587
    s.smtp_user = None
    s.smtp_password = None
    s.smtp_tls = True
    s.emails_from_email = None
    s.emails_from_name = None
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(s, k, v)
    return s


class TestCompanySettings:
    def test_get_settings_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_for_owner = AsyncMock(side_effect=NotFoundError("Company settings not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_company_settings_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/company-settings/")
        assert r.status_code == 404

    def test_get_settings(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_for_owner = AsyncMock(return_value=_settings({"name": "My Company"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_company_settings_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/company-settings/")
        assert r.status_code == 200
        assert r.json()["name"] == "My Company"

    def test_create_settings(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_settings())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_company_settings_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/company-settings/",
            json={"name": "New Co"},
        )
        assert r.status_code == 201

    def test_upsert_settings(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.upsert = AsyncMock(return_value=_settings())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_company_settings_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/company-settings/",
            json={"name": "Updated Co"},
        )
        assert r.status_code == 200

    def test_delete_settings(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_company_settings_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/company-settings/")
        assert r.status_code == 204
