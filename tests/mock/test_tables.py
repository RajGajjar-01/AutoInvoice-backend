import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _table(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.name = "Test"
    m.columns = []
    m.description = None
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


class TestTables:
    def test_list_tables(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([], 0))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/tables/")
        assert r.status_code == 200

    def test_create_table(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_table())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/",
            json={"name": "Test Table", "columns": [{"name": "col1", "type": "text"}]},
        )
        assert r.status_code == 201

    def test_create_table_duplicate_columns(self, client: TestClient, mock_user):
        from app.exceptions import ValidationError
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(side_effect=ValidationError("Column names must be unique"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/",
            json={"name": "Bad", "columns": [{"name": "col1", "type": "text"}, {"name": "col1", "type": "number"}]},
        )
        assert r.status_code == 422

    def test_get_table(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_table_with_rows = AsyncMock(return_value=_table())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_get_table_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_table_with_rows = AsyncMock(side_effect=NotFoundError("Table not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_update_table(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_table({"name": "Updated"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.patch(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}", json={"name": "Updated"})
        assert r.status_code == 200

    def test_delete_table(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_duplicate_table(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.duplicate = AsyncMock(return_value=_table({"name": "Test (Copy)"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/duplicate")
        assert r.status_code == 200


def _row(overrides=None):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.table_id = uuid.uuid4()
    r.data = {"col1": "val1"}
    r.created_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(r, k, v)
    return r


def _reminder(overrides=None):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.table_id = uuid.uuid4()
    r.reminder_data = {"note": "test"}
    r.created_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(r, k, v)
    return r


class TestTableRows:
    def test_create_row(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.add_row = AsyncMock(return_value=_row())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/rows",
            json={"data": {"col1": "val1"}},
        )
        assert r.status_code == 201

    def test_create_row_missing_mandatory(self, client: TestClient, mock_user):
        from app.exceptions import ValidationError
        mock_svc = AsyncMock()
        mock_svc.add_row = AsyncMock(side_effect=ValidationError("Missing mandatory fields: name"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/rows",
            json={"data": {}},
        )
        assert r.status_code == 422

    def test_update_row(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update_row = AsyncMock(return_value=_row())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/rows/{uuid.uuid4()}",
            json={"data": {"col1": "updated"}},
        )
        assert r.status_code == 200

    def test_delete_row(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete_row = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/rows/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_bulk_delete_rows(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.bulk_delete_rows = AsyncMock(return_value=2)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/rows/bulk-delete",
            json=[str(uuid.uuid4()), str(uuid.uuid4())],
        )
        assert r.status_code == 200
        assert r.json()["deleted"] == 2


class TestTableReminders:
    def test_create_reminder(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.add_reminder = AsyncMock(return_value=_reminder())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/reminders",
            json={"reminder_data": {"note": "test"}},
        )
        assert r.status_code == 201

    def test_delete_reminder(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete_reminder = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_table_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/tables/{uuid.uuid4()}/reminders/{uuid.uuid4()}")
        assert r.status_code == 204
