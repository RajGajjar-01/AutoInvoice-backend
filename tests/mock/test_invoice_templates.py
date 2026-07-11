import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _template(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.name = "Default Template"
    m.kind = "built_in"
    m.is_active = True
    m.built_in_id = "classic"
    m.custom_data = None
    m.imported_html = None
    m.imported_pdf_data_url = None
    m.imported_excel_columns = None
    m.imported_excel_data = None
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


class TestTemplateList:
    def test_list_templates(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.list_items = AsyncMock(return_value=([_template()], 1))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoice-templates/")
        assert r.status_code == 200

    def test_get_active(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_active = AsyncMock(return_value=_template())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoice-templates/active")
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_get_active_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_active = AsyncMock(side_effect=NotFoundError("No active invoice template"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoice-templates/active")
        assert r.status_code == 404


class TestTemplateGet:
    def test_get_template(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(return_value=_template())
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoice-templates/{uuid.uuid4()}")
        assert r.status_code == 200

    def test_get_template_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError
        mock_svc = AsyncMock()
        mock_svc.get_owned = AsyncMock(side_effect=NotFoundError("Invoice template not found"))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.get(f"{settings.API_V1_STR}/invoice-templates/{uuid.uuid4()}")
        assert r.status_code == 404


class TestTemplateCreate:
    def test_create_template(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=_template({"name": "New Template"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.post(
            f"{settings.API_V1_STR}/invoice-templates/",
            json={"name": "New Template", "kind": "built_in", "built_in_id": "modern"},
        )
        assert r.status_code == 201
        assert r.json()["name"] == "New Template"


class TestTemplateUpdate:
    def test_update_template(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=_template({"name": "Updated"}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.put(
            f"{settings.API_V1_STR}/invoice-templates/{uuid.uuid4()}",
            json={"name": "Updated"},
        )
        assert r.status_code == 200


class TestTemplateActivate:
    def test_activate_template(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.activate = AsyncMock(return_value=_template({"is_active": True}))
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.post(f"{settings.API_V1_STR}/invoice-templates/{uuid.uuid4()}/activate")
        assert r.status_code == 200
        assert r.json()["is_active"] is True


class TestTemplateDelete:
    def test_delete_template(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_template_service] = lambda: mock_svc

        r = client.delete(f"{settings.API_V1_STR}/invoice-templates/{uuid.uuid4()}")
        assert r.status_code == 204


class TestParseExcel:
    def test_parse_excel_no_file(self, client: TestClient, mock_user):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        r = client.post(f"{settings.API_V1_STR}/invoice-templates/parse-excel")
        assert r.status_code == 422

    def test_parse_excel_invalid_extension(self, client: TestClient, mock_user):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        r = client.post(
            f"{settings.API_V1_STR}/invoice-templates/parse-excel",
            files={"file": ("test.txt", b"data", "text/plain")},
        )
        assert r.status_code == 400
