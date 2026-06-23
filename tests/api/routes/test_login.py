import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.utils import random_email, random_lower_string


def test_get_access_token(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": settings.FIRST_SUPERUSER, "password": "incorrect"},
    )
    assert r.status_code == 400


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    result = r.json()
    assert "email" in result


def test_signup(client: TestClient, db: Session) -> None:
    email = random_email()
    r = client.post(
        f"{settings.API_V1_STR}/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "New User",
        },
    )
    assert r.status_code == 200
    result = r.json()
    assert "access_token" in result
    assert "user" in result
    assert result["user"]["email"] == email


def test_signup_existing_user(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/auth/signup",
        json={
            "email": settings.FIRST_SUPERUSER,
            "password": "password123",
            "full_name": "Duplicate User",
        },
    )
    assert r.status_code == 400


def test_refresh_token(client: TestClient) -> None:
    login_r = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert login_r.status_code == 200

    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token is not None

    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
    )
    assert r.status_code == 200
    result = r.json()
    assert "access_token" in result


def test_logout(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/auth/logout",
    )
    assert r.status_code == 200
    assert "message" in r.json()


try:
    from pwdlib.hashers.bcrypt import BcryptHasher  # noqa: F401

    _bcrypt_available = True
except Exception:
    _bcrypt_available = False


@pytest.mark.skipif(not _bcrypt_available, reason="pip install pwdlib[bcrypt]")
def test_login_upgrades_bcrypt_hash_to_argon2(client: TestClient, db: Session) -> None:
    from pwdlib.hashers.bcrypt import BcryptHasher

    from app.core.security import verify_password
    from app.models import User

    email = random_email()
    password = random_lower_string()

    bcrypt_hash = BcryptHasher().hash(password)
    assert bcrypt_hash.startswith("$2")

    user = User(email=email, hashed_password=bcrypt_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.hashed_password.startswith("$2")

    response = client.post(
        f"{settings.API_V1_STR}/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200

    db.refresh(user)
    assert user.hashed_password.startswith("$argon2")
    verified, updated_hash = verify_password(password, user.hashed_password)
    assert verified
    assert updated_hash is None
