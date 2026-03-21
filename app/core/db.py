from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    """
    Initialize database.

    With Supabase Auth, users are created in Supabase and synced to
    the local profiles table via JWT verification or triggers.

    This function is kept for compatibility but doesn't create users
    locally anymore - Supabase handles all user creation.
    """
    pass
