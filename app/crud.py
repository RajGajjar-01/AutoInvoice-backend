import uuid
from typing import Any

from sqlmodel import Session, func, select

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create,
        update={
            "email": normalize_email(user_create.email),
            "hashed_password": get_password_hash(user_create.password),
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data: dict[str, Any] = {}
    if user_data.get("email"):
        user_data["email"] = normalize_email(user_data["email"])
    if user_data.get("password"):
        extra_data["hashed_password"] = get_password_hash(user_data["password"])
    # Changing credentials, the account email or privileges, or deactivating the
    # account, revokes every outstanding session token.
    sensitive = {"password", "email", "is_active", "is_superuser"}
    if any(
        k in user_data and user_data[k] != getattr(db_user, k, None) for k in sensitive
    ):
        extra_data["token_version"] = db_user.token_version + 1
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def set_user_password(*, session: Session, db_user: User, password: str) -> User:
    """Set a new password and revoke all existing sessions for the user."""
    db_user.hashed_password = get_password_hash(password)
    db_user.token_version += 1
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def revoke_user_tokens(*, session: Session, db_user: User) -> None:
    db_user.token_version += 1
    session.add(db_user)
    session.commit()


def get_user_by_email(*, session: Session, email: str) -> User | None:
    # Case-insensitive so "Victim@x.com" and "victim@x.com" are one account.
    statement = select(User).where(func.lower(User.email) == normalize_email(email))
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item
