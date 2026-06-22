from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from app.schemas import UserCreate
from tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password},
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {client.cookies.get('access_token')}"}


def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_lower_string()
    user_create = UserCreate(
        email=email,
        password=password,
        full_name=random_lower_string(),
    )
    user = crud.create_user(session=db, user_create=user_create)
    return user


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session, password: str = "testpassword123"
) -> dict[str, str]:
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        user_create = UserCreate(
            email=email,
            password=password,
            full_name=random_lower_string(),
        )
        user = crud.create_user(session=db, user_create=user_create)

    return user_authentication_headers(client=client, email=email, password=password)
