from fastapi.testclient import TestClient

from app.core.config import settings


def test_create_and_list_notifications(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"title": "Test notification", "type": "info"}
    create_response = client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert create_response.status_code == 200
    notification_id = create_response.json()["id"]

    list_response = client.get(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers
    )
    assert list_response.status_code == 200
    content = list_response.json()
    assert content["count"] >= 1
    assert any(n["id"] == notification_id for n in content["data"])


def test_update_mark_read_and_delete(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"title": "Another notification", "type": "info"}
    create_response = client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers,
        json=data,
    )
    notification_id = create_response.json()["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers,
        json={"read": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["read"] is True

    delete_response = client.delete(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Notification deleted successfully"


def test_mark_all_read_and_clear_all(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for _ in range(2):
        client.post(
            f"{settings.API_V1_STR}/notifications/",
            headers=normal_user_token_headers,
            json={"title": "n", "type": "info"},
        )

    mark_response = client.post(
        f"{settings.API_V1_STR}/notifications/mark-all-read",
        headers=normal_user_token_headers,
    )
    assert mark_response.status_code == 200

    clear_response = client.delete(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers
    )
    assert clear_response.status_code == 200
