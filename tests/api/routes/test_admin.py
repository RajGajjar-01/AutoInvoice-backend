import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
from tests.utils.utils import random_email, random_lower_string


def test_admin_create_list_and_get_user(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    email = random_email()
    create_response = client.post(
        f"{settings.API_V1_STR}/admin/users",
        headers=superuser_token_headers,
        json={"email": email, "password": random_lower_string(), "full_name": "Admin Created"},
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]

    list_response = client.get(
        f"{settings.API_V1_STR}/admin/users", headers=superuser_token_headers
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    get_response = client.get(
        f"{settings.API_V1_STR}/admin/users/{user_id}", headers=superuser_token_headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["email"] == email


def test_admin_get_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_admin_update_user(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/admin/users",
        headers=superuser_token_headers,
        json={"email": random_email(), "password": random_lower_string()},
    )
    user_id = create_response.json()["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/admin/users/{user_id}",
        headers=superuser_token_headers,
        json={"full_name": "Updated By Admin", "is_active": False},
    )
    assert update_response.status_code == 200
    content = update_response.json()
    assert content["full_name"] == "Updated By Admin"
    assert content["is_active"] is False


def test_admin_delete_user_self_forbidden(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert superuser is not None
    response = client.delete(
        f"{settings.API_V1_STR}/admin/users/{superuser.id}", headers=superuser_token_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Super users are not allowed to delete themselves"
