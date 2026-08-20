from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User
from app.schemas import UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
async_engine: AsyncEngine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI)
)


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        db_obj = User.model_validate(
            user_in, update={"hashed_password": get_password_hash(user_in.password)}
        )
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
