import uuid

from sqlmodel import Session

from app.models import Item
from app.schemas import ItemCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_item(db: Session, owner_id: uuid.UUID | None = None) -> Item:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id
        assert owner_id is not None

    name = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(name=name, description=description)
    item = Item.model_validate(item_in, update={"owner_id": owner_id})
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
