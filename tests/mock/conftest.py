import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@test.com"
    user.is_active = True
    user.is_superuser = False
    user.hashed_password = "$argon2id$v=19$m=65536,t=3,p=4$hash"
    user.full_name = "Test User"
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.is_verified = True
    user.avatar_url = None
    user.google_email = None
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_token_expires_at = None
    user.google_connected = False
    return user


@pytest.fixture
def mock_superuser() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@test.com"
    user.is_active = True
    user.is_superuser = True
    user.hashed_password = "$argon2id$v=19$m=65536,t=3,p=4$hash"
    user.full_name = "Admin User"
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.is_verified = True
    user.avatar_url = None
    user.google_email = None
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_token_expires_at = None
    user.google_connected = False
    return user


@pytest.fixture(autouse=True)
def _clear_overrides_after() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()
