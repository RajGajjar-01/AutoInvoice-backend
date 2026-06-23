import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.customer import create_random_customer
from tests.utils.utils import random_lower_string


def test_create_customer(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    data = {"name": random_lower_string()}
    response = client.post(
        f"{settings.API_V1_STR}/customers/", headers=normal_user_token_headers, json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert "id" in content


def test_read_customer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    customer = create_random_customer(db)
    response = client.get(
        f"{settings.API_V1_STR}/customers/{customer.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 403


def test_read_customer_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/customers/{uuid.uuid4()}", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_update_and_delete_customer(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": random_lower_string()}
    create_response = client.post(
        f"{settings.API_V1_STR}/customers/", headers=normal_user_token_headers, json=data
    )
    customer_id = create_response.json()["id"]

    update_data = {"name": "updated name"}
    update_response = client.put(
        f"{settings.API_V1_STR}/customers/{customer_id}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "updated name"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/customers/{customer_id}", headers=normal_user_token_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Customer deleted successfully"
