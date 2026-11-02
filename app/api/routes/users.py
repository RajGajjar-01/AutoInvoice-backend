import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    LimitDep,
    SessionDep,
    SkipDep,
    get_current_active_superuser,
)
from app.core import rate_limit
from app.core.config import settings
from app.core.security import verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

logger = logging.getLogger("app.security")

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: SkipDep = 0, limit: LimitDep = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    return UsersPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        # Never email the password itself.
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    user_data = user_in.model_dump(exclude_unset=True, exclude={"current_password"})
    if user_in.email and crud.normalize_email(user_in.email) != current_user.email:
        # Re-authenticate before changing the address that password recovery
        # goes to; otherwise a stolen session becomes a permanent takeover.
        verified = (
            bool(user_in.current_password)
            and verify_password(
                user_in.current_password or "", current_user.hashed_password
            )[0]
        )
        if not verified:
            raise HTTPException(
                status_code=400,
                detail="Current password is required to change the email address",
            )
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
        user_data["email"] = crud.normalize_email(user_in.email)
        logger.info("email_changed user_id=%s", current_user.id)
    else:
        user_data.pop("email", None)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    # Revokes all existing sessions (including this one); the client must log in
    # again with the new password.
    crud.set_user_password(
        session=session, db_user=current_user, password=body.new_password
    )
    logger.info("password_changed user_id=%s", current_user.id)
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


SIGNUP_MESSAGE = (
    "If this email address can be registered, the account has been created. "
    "You can now log in."
)


@router.post("/signup", response_model=Message)
def register_user(request: Request, session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.

    The response is identical whether or not the email is already registered so
    that signup cannot be used to discover which addresses have accounts.
    """
    ip = rate_limit.client_ip(request)
    rate_limit.enforce(f"signup-ip:{ip}", settings.SIGNUP_RATE_LIMIT_PER_IP)
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        logger.info("signup_existing_email ip=%s", ip)
        if settings.emails_enabled:
            send_email(
                email_to=user.email,
                subject=f"{settings.PROJECT_NAME} - Sign-up attempt",
                html_content=(
                    "<p>Someone tried to create an account with this email address. "
                    "If this was you, log in or use password recovery instead. "
                    "Otherwise you can ignore this message.</p>"
                ),
            )
        return Message(message=SIGNUP_MESSAGE)
    user_create = UserCreate.model_validate(user_in)
    crud.create_user(session=session, user_create=user_create)
    return Message(message=SIGNUP_MESSAGE)


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
