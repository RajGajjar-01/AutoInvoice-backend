from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import Item, Profile
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", str(settings.SQLALCHEMY_DATABASE_URI))
    command.upgrade(alembic_cfg, "head")
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(Profile)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="function")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture
def mock_supabase_auth():
    """Mock Supabase auth for testing."""
    with patch("app.core.supabase_client.get_supabase_client") as mock_client:
        client = MagicMock()
        mock_client.return_value = client

        client.auth = MagicMock()
        client.auth.sign_up = AsyncMock()
        client.auth.sign_in_with_password = AsyncMock()
        client.auth.sign_out = AsyncMock()
        client.auth.get_user = AsyncMock()
        client.auth.get_session = AsyncMock()
        client.auth.refresh_session = AsyncMock()
        client.auth.reset_password_email = AsyncMock()
        client.auth.update_user = AsyncMock()
        client.auth.resend = AsyncMock()

        yield client


@pytest.fixture
def mock_supabase_admin():
    """Mock Supabase admin client for testing."""
    with patch("app.core.supabase_client.get_supabase_admin_client") as mock_admin:
        admin = MagicMock()
        mock_admin.return_value = admin

        admin.auth = MagicMock()
        admin.auth.admin = MagicMock()
        admin.auth.admin.list_users = AsyncMock()
        admin.auth.admin.get_user_by_id = AsyncMock()
        admin.auth.admin.create_user = AsyncMock()
        admin.auth.admin.update_user_by_id = AsyncMock()
        admin.auth.admin.delete_user = AsyncMock()

        yield admin
