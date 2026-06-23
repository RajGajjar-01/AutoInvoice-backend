from fastapi.testclient import TestClient

from app.core.config import settings


def test_get_company_settings_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_create_then_conflict(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Acme Inc"}
    first = client.post(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers, json=data
    )
    assert first.status_code == 200
    assert first.json()["name"] == "Acme Inc"

    second = client.post(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers, json=data
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Company settings already exist"


def test_upsert_and_delete(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    update_response = client.put(
        f"{settings.API_V1_STR}/company-settings/",
        headers=normal_user_token_headers,
        json={"name": "Upserted Co"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Upserted Co"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Company settings deleted successfully"
