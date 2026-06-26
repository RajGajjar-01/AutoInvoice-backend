import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _invoice(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.customer_id = uuid.uuid4()
    m.invoice_number = "INV-001"
    m.document_type = "invoice"
    m.invoice_date = "2024-01-15"
    m.due_date = "2024-02-15"
    m.valid_until = None
    m.currency = "INR"
    m.subtotal = 1000.0
    m.total_tax = 180.0
    m.grand_total = 1180.0
    m.discount = 0.0
    m.notes = None
    m.payment_terms = None
    m.status = "unpaid"
    m.place_of_supply = None
    m.reverse_charge = False
    m.items = []
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    m.customer = None
    m.customer_name = None
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


class TestInvoiceList:
    def test_list_invoices(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([_invoice()], 1))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoices/")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1

    def test_list_with_filters(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([], 0))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoices/?status=paid&document_type=invoice")
        assert r.status_code == 200


class TestInvoiceGet:
    def test_get_invoice(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_with_customer = AsyncMock(return_value=_invoice())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_get_invoice_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_with_customer = AsyncMock(side_effect=NotFoundError("Invoice not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}")
        assert r.status_code == 404


class TestInvoiceCreate:
    def test_create_invoice(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_invoice())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/invoices/",
            json={
                "invoice_number": "INV-001",
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2024-01-15",
                "items": [{"name": "Item", "quantity": 1, "price": 100}],
            },
        )
        assert r.status_code == 201


class TestInvoiceUpdate:
    def test_update_invoice(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_invoice({"status": "paid"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}",
            json={"status": "paid"},
        )
        assert r.status_code == 200

    def test_update_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(side_effect=NotFoundError("Invoice not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.put(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}", json={"status": "paid"})
        assert r.status_code == 404


class TestInvoiceDelete:
    def test_delete_invoice(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_delete_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(side_effect=NotFoundError("Invoice not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}")
        assert r.status_code == 404


class TestInvoiceStats:
    def test_dashboard_stats(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_dashboard_stats = AsyncMock(return_value={
            "total_invoices": 10,
            "paid_count": 5,
            "unpaid_count": 3,
            "overdue_count": 2,
            "total_customers": 8,
            "total_revenue": 50000.0,
        })
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoices/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_invoices"] == 10
        assert data["total_revenue"] == 50000.0
