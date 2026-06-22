import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, SuperUserDep
from app.models import User
from app.schemas import Message, UserPublic, UserUpdate, UserUpdateMe, UsersPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UsersPublic)
def read_users(
    session: SessionDep,
    superuser: SuperUserDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    return UsersPublic(
        data=[UserPublic.model_validate(u) for u in users],
        count=count,
    )


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    session: SessionDep,
    current_user: CurrentUser,
    user_in: UserUpdateMe,
) -> Any:
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name

    if user_in.email is not None and user_in.email != current_user.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists",
            )
        current_user.email = user_in.email
        current_user.is_verified = False

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return UserPublic.model_validate(current_user)


@router.delete("/me", response_model=Message)
def delete_user_me(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Super users are not allowed to delete themselves",
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )

    return UserPublic.model_validate(user)


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: uuid.UUID,
    session: SessionDep,
    superuser: SuperUserDep,
    user_in: UserUpdate,
) -> Any:
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

    crud.update_user(session=session, db_user=user, user_in=user_in)
    return UserPublic.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
def delete_user(
    session: SessionDep,
    superuser: SuperUserDep,
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
