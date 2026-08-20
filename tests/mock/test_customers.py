import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _customer(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.name = "Test Customer"
    m.party_type = "customer"
    m.phone = "1234567890"
    m.whatsapp = None
    m.email = "customer@test.com"
    m.billing_address = "123 Street"
    m.shipping_address = None
    m.address = "123 Street, City"
    m.gstin = "GSTIN123"
    m.gst = None
    m.state = "Maharashtra"
    m.tags = []
    m.opening_balance = 0.0
    m.credit_limit = None
    m.payment_terms = None
    m.notes = None
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


class TestCustomers:
    def test_list_customers(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([_customer()], 1))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/customers/")
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_get_customer(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(return_value=_customer())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/customers/{uuid.uuid4()}")
        assert r.status_code == 200
        assert r.json()["name"] == "Test Customer"

    def test_get_customer_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(side_effect=NotFoundError("Customer not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/customers/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_get_customer_forbidden(self, client: TestClient, mock_user):
        from app.exceptions import ForbiddenError

        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(
            side_effect=ForbiddenError("Not enough permissions")
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/customers/{uuid.uuid4()}")
        assert r.status_code == 403

    def test_create_customer(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_customer())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/customers/",
            json={"name": "New Customer"},
        )
        assert r.status_code == 201

    def test_update_customer(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_customer({"name": "Updated"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/customers/{uuid.uuid4()}",
            json={"name": "Updated"},
        )
        assert r.status_code == 200

    def test_delete_customer(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/customers/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_delete_customer_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(side_effect=NotFoundError("Customer not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_customer_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/customers/{uuid.uuid4()}")
        assert r.status_code == 404
