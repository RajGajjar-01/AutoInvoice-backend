import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _item(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.name = "Test Item"
    m.description = "A test item"
    m.category = "General"
    m.sku = "SKU-001"
    m.unit = "pcs"
    m.price = 100.0
    m.tax_rate = 18.0
    m.stock = 50.0
    m.low_stock_threshold = 5.0
    m.stock_history = []
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


class TestItemList:
    def test_list_items(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(
            return_value=([_item(), _item({"name": "Item 2"})], 2)
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/items/")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert len(data["data"]) == 2

    def test_list_items_with_filters(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([_item()], 1))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(
            f"{settings.API_V1_STR}/items/?search=test&category=General&stock_status=in_stock"
        )
        assert r.status_code == 200


class TestItemGet:
    def test_get_item(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(return_value=_item())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/items/{uuid.uuid4()}")
        assert r.status_code == 200
        assert r.json()["name"] == "Test Item"

    def test_get_item_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(side_effect=NotFoundError("Item not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/items/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_get_item_forbidden(self, client: TestClient, mock_user):
        from app.exceptions import ForbiddenError

        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(
            side_effect=ForbiddenError("Not enough permissions")
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/items/{uuid.uuid4()}")
        assert r.status_code == 403


class TestItemCreate:
    def test_create_item(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_item({"name": "New Item"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/items/",
            json={"name": "New Item", "price": 50.0},
        )
        assert r.status_code == 201
        assert r.json()["name"] == "New Item"


class TestItemUpdate:
    def test_update_item(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_item({"name": "Updated"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
            json={"name": "Updated"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

    def test_update_item_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(side_effect=NotFoundError("Item not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/items/{uuid.uuid4()}", json={"name": "X"}
        )
        assert r.status_code == 404


class TestItemDelete:
    def test_delete_item(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/items/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_delete_item_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(side_effect=NotFoundError("Item not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/items/{uuid.uuid4()}")
        assert r.status_code == 404


class TestItemCategories:
    def test_list_categories(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_categories = AsyncMock(return_value=["General", "Electronics"])
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/items/categories/list")
        assert r.status_code == 200
        assert r.json() == ["General", "Electronics"]


class TestItemAdjustStock:
    def test_adjust_stock(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.adjust_stock = AsyncMock(return_value=_item({"stock": 60.0}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.patch(
            f"{settings.API_V1_STR}/items/{uuid.uuid4()}/adjust-stock?quantity=10",
        )
        assert r.status_code == 200

    def test_adjust_stock_insufficient(self, client: TestClient, mock_user):
        from app.exceptions import ValidationError

        mock_svc = AsyncMock()
        mock_svc.adjust_stock = AsyncMock(
            side_effect=ValidationError("Insufficient stock")
        )
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_item_service] = lambda: mock_svc

        r = client.patch(
            f"{settings.API_V1_STR}/items/{uuid.uuid4()}/adjust-stock?quantity=-999",
        )
        assert r.status_code == 422
