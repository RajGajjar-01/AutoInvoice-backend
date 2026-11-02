from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import Item, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolate_auth_state(client: TestClient) -> Generator[None, None, None]:
    # Rate limiting is exercised by dedicated tests; keep it out of the way of
    # the rest of the suite. Also drop cookies so each test authenticates only
    # with the headers it passes explicitly.
    previous = settings.RATE_LIMIT_ENABLED
    settings.RATE_LIMIT_ENABLED = False
    limiter.reset()
    client.cookies.clear()
    yield
    settings.RATE_LIMIT_ENABLED = previous
    limiter.reset()
    client.cookies.clear()


# Function-scoped: changing a password revokes the user's existing tokens, so
# every test gets a freshly issued token.
@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
