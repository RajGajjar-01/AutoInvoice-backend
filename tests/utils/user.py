from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import get_password_hash
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
    user_in = UserCreate(email=email, password=password, full_name=random_lower_string())
    db_obj = User.model_validate(
        user_in, update={"hashed_password": get_password_hash(user_in.password)}
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session, password: str = "testpassword123"
) -> dict[str, str]:
    user = db.exec(select(User).where(User.email == email)).first()
    if not user:
        user_in = UserCreate(email=email, password=password, full_name=random_lower_string())
        db_obj = User.model_validate(
            user_in, update={"hashed_password": get_password_hash(user_in.password)}
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

    return user_authentication_headers(client=client, email=email, password=password)
