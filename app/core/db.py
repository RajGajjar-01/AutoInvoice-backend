from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly


def init_db(session: Session) -> None:
    # Create all tables if they don't exist yet.
    # This is a safety net for development — Alembic migrations are the preferred
    # approach, but if someone hasn't run "alembic upgrade head" yet (or is starting
    # fresh without running prestart.sh), this ensures the app works anyway.
    SQLModel.metadata.create_all(engine)
    # create_all() does not add columns to existing tables. Make sure databases
    # created before session revocation existed get the token_version column
    # (the Alembic migration b7c1d2e3f4a5 does the same).
    columns = {c["name"] for c in inspect(engine).get_columns("user")}
    if "token_version" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text(
                    'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS token_version '
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
