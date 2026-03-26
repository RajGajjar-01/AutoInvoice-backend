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
