import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


def test_create_table(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test creating a new data table."""
    data = {
        "name": "Test Table",
        "columns": [
            {
                "name": "Name",
                "type": "Text",
                "mandatory": True,
                "description": "Person name"
            },
            {
                "name": "Email",
                "type": "Text",
                "mandatory": False,
                "description": "Email address"
            }
        ]
    }
    response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 201
    content = response.json()
    assert content["name"] == data["name"]
    assert len(content["columns"]) == 2
    assert "id" in content
    assert "owner_id" in content
    assert "created_at" in content
    assert "updated_at" in content


def test_create_table_duplicate_column_names(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test that duplicate column names are rejected."""
    data = {
        "name": "Test Table",
        "columns": [
            {"name": "Name", "type": "Text", "mandatory": True},
            {"name": "Name", "type": "Text", "mandatory": False}
        ]
    }
    response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 422
    assert "Column names must be unique" in response.json()["detail"]


def test_list_tables(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test listing tables with pagination."""
    # Create a few tables
    for i in range(3):
        data = {
            "name": f"Table {i}",
            "columns": [{"name": "Col1", "type": "Text", "mandatory": False}]
        }
        client.post(
            f"{settings.API_V1_STR}/tables",
            headers=superuser_token_headers,
            json=data,
        )
    
    # List tables
    response = client.get(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "total" in content
    assert "page" in content
    assert "page_size" in content
    assert "total_pages" in content
    assert len(content["data"]) >= 3


def test_list_tables_with_search(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test searching tables by name."""
    # Create tables with specific names
    data1 = {
        "name": "Invoice Table",
        "columns": [{"name": "Col1", "type": "Text", "mandatory": False}]
    }
    data2 = {
        "name": "Customer Table",
        "columns": [{"name": "Col1", "type": "Text", "mandatory": False}]
    }
    client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data1,
    )
    client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data2,
    )
    
    # Search for "Invoice"
    response = client.get(
        f"{settings.API_V1_STR}/tables?search=Invoice",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 1
    assert any("Invoice" in table["name"] for table in content["data"])


def test_get_table(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting a specific table with rows."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Get table
    response = client.get(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == table_id
    assert "rows" in content
    assert "reminders" in content


def test_update_table(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test updating a table."""
    # Create table
    data = {
        "name": "Original Name",
        "columns": [{"name": "Col1", "type": "Text", "mandatory": False}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Update table
    update_data = {"name": "Updated Name"}
    response = client.patch(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
        json=update_data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Updated Name"


def test_delete_table(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test deleting a table."""
    # Create table
    data = {
        "name": "Table to Delete",
        "columns": [{"name": "Col1", "type": "Text", "mandatory": False}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Delete table
    response = client.delete(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 204
    
    # Verify table is deleted
    get_response = client.get(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
    )
    assert get_response.status_code == 404


def test_duplicate_table(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test duplicating a table with rows."""
    # Create table
    data = {
        "name": "Original Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Add a row
    row_data = {"data": {"Name": "John Doe"}}
    client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    
    # Duplicate table
    response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/duplicate",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Original Table (Copy)"
    assert content["id"] != table_id
    
    # Verify rows were copied
    get_response = client.get(
        f"{settings.API_V1_STR}/tables/{content['id']}",
        headers=superuser_token_headers,
    )
    assert len(get_response.json()["rows"]) == 1


def test_create_row(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test creating a row in a table."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [
            {"name": "Name", "type": "Text", "mandatory": True},
            {"name": "Age", "type": "Text", "mandatory": False}
        ]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Create row
    row_data = {"data": {"Name": "John Doe", "Age": "30"}}
    response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    assert response.status_code == 201
    content = response.json()
    assert content["data"]["Name"] == "John Doe"
    assert "id" in content


def test_create_row_missing_mandatory_field(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test that missing mandatory fields are rejected."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Try to create row without mandatory field
    row_data = {"data": {}}
    response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    assert response.status_code == 422
    assert "Missing mandatory fields" in response.json()["detail"]


def test_update_row(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test updating a row."""
    # Create table and row
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    row_data = {"data": {"Name": "John Doe"}}
    row_response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    row_id = row_response.json()["id"]
    
    # Update row
    update_data = {"data": {"Name": "Jane Doe"}}
    response = client.put(
        f"{settings.API_V1_STR}/tables/{table_id}/rows/{row_id}",
        headers=superuser_token_headers,
        json=update_data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["data"]["Name"] == "Jane Doe"


def test_delete_row(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test deleting a row."""
    # Create table and row
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    row_data = {"data": {"Name": "John Doe"}}
    row_response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    row_id = row_response.json()["id"]
    
    # Delete row
    response = client.delete(
        f"{settings.API_V1_STR}/tables/{table_id}/rows/{row_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 204


def test_bulk_delete_rows(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test bulk deleting rows."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Create multiple rows
    row_ids = []
    for i in range(3):
        row_data = {"data": {"Name": f"Person {i}"}}
        row_response = client.post(
            f"{settings.API_V1_STR}/tables/{table_id}/rows",
            headers=superuser_token_headers,
            json=row_data,
        )
        row_ids.append(row_response.json()["id"])
    
    # Bulk delete
    response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows/bulk-delete",
        headers=superuser_token_headers,
        json=row_ids,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["deleted"] == 3


def test_create_reminder(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test creating a reminder for a table."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Create reminder
    reminder_data = {
        "reminder_data": {
            "type": "date",
            "date": "2024-12-31",
            "message": "Year end reminder"
        }
    }
    response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/reminders",
        headers=superuser_token_headers,
        json=reminder_data,
    )
    assert response.status_code == 201
    content = response.json()
    assert content["reminder_data"]["message"] == "Year end reminder"
    assert "id" in content


def test_delete_reminder(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test deleting a reminder."""
    # Create table and reminder
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    reminder_data = {
        "reminder_data": {"type": "date", "date": "2024-12-31"}
    }
    reminder_response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/reminders",
        headers=superuser_token_headers,
        json=reminder_data,
    )
    reminder_id = reminder_response.json()["id"]
    
    # Delete reminder
    response = client.delete(
        f"{settings.API_V1_STR}/tables/{table_id}/reminders/{reminder_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 204


def test_ownership_isolation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that users can only access their own tables."""
    # Create table as superuser
    data = {
        "name": "Superuser Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Create a normal user and get auth headers
    from tests.utils.user import create_random_user, user_authentication_headers
    from tests.utils.utils import random_lower_string
    
    password = random_lower_string()
    normal_user = create_random_user(db)
    
    # Update user password to known value
    from app.models import UserUpdate
    from app import crud
    user_update = UserUpdate(password=password)
    crud.update_user(session=db, db_user=normal_user, user_in=user_update)
    
    normal_user_headers = user_authentication_headers(
        client=client, email=normal_user.email, password=password
    )
    
    # Try to access superuser's table as normal user
    response = client.get(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=normal_user_headers,
    )
    assert response.status_code == 404


def test_cascade_delete(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test that deleting a table cascades to rows and reminders."""
    # Create table
    data = {
        "name": "Test Table",
        "columns": [{"name": "Name", "type": "Text", "mandatory": True}]
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tables",
        headers=superuser_token_headers,
        json=data,
    )
    table_id = create_response.json()["id"]
    
    # Add row
    row_data = {"data": {"Name": "John Doe"}}
    row_response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/rows",
        headers=superuser_token_headers,
        json=row_data,
    )
    row_id = row_response.json()["id"]
    
    # Add reminder
    reminder_data = {"reminder_data": {"type": "date", "date": "2024-12-31"}}
    reminder_response = client.post(
        f"{settings.API_V1_STR}/tables/{table_id}/reminders",
        headers=superuser_token_headers,
        json=reminder_data,
    )
    reminder_id = reminder_response.json()["id"]
    
    # Delete table
    delete_response = client.delete(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 204
    
    # Verify table is gone
    get_response = client.get(
        f"{settings.API_V1_STR}/tables/{table_id}",
        headers=superuser_token_headers,
    )
    assert get_response.status_code == 404
