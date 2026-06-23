import uuid

from sqlmodel import Session

from app.models import Customer
from app.schemas import CustomerCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_customer(db: Session, owner_id: uuid.UUID | None = None) -> Customer:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id
        assert owner_id is not None

    customer_in = CustomerCreate(name=random_lower_string())
    customer = Customer.model_validate(customer_in, update={"owner_id": owner_id})
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer
