import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import EmailStr
from sqlmodel import SQLModel

from app import crud
from app.api.deps import SessionDep, SuperUserDep
from app.core.security import get_password_hash
from app.models import User
from app.schemas import Message, PaginatedResponse, UserCreate, UserPublic, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserCreate(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    is_superuser: bool = False


class AdminUserUpdate(SQLModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


@router.get("/users", response_model=PaginatedResponse[UserPublic])
def list_users(
    session: SessionDep,
    superuser: SuperUserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> PaginatedResponse[UserPublic]:
    from sqlmodel import col, func, select

    count_statement = select(func.count()).select_from(User)
    total = session.exec(count_statement).one()

    offset = (page - 1) * page_size
    statement = (
        select(User)
        .order_by(col(User.created_at).desc())
        .offset(offset)
        .limit(page_size)
    )
    users = session.exec(statement).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        data=[UserPublic.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/users", response_model=UserPublic)
def create_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_in: AdminUserCreate,
) -> UserPublic:
    existing_user = crud.get_user_by_email(session=session, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )

    user_create = UserCreate(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
    )
    user = crud.create_user(session=session, user_create=user_create)

    return UserPublic.model_validate(user)


@router.get("/users/{user_id}", response_model=UserPublic)
def get_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_id: uuid.UUID,
) -> UserPublic:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: AdminUserUpdate,
) -> UserPublic:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.email and user_in.email != user.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists",
            )
        user.email = user_in.email
        user.is_verified = False

    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    if user_in.full_name is not None:
        user.full_name = user_in.full_name

    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser

    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    session.add(user)
    session.commit()
    session.refresh(user)

    return UserPublic.model_validate(user)


@router.delete("/users/{user_id}", response_model=Message)
def delete_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_id: uuid.UUID,
) -> Message:
    if user_id == superuser.id:
        raise HTTPException(
            status_code=403,
            detail="Super users are not allowed to delete themselves",
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()

    return Message(message="User deleted successfully")
