from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app import crud
from app.api.deps import SessionDep
from app.models import User
from app.schemas import UserCreate, UserPublic

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_verified: bool = False
    is_superuser: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    user_create = UserCreate(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
    )
    user = crud.create_user(session=session, user_create=user_create)

    if user_in.is_verified:
        user.is_verified = True
        session.add(user)
        session.commit()
        session.refresh(user)

    return UserPublic.model_validate(user)
