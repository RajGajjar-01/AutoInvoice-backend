import structlog
from sqlmodel import Session

from app.core.db import engine, init_db

logger = structlog.get_logger(__name__)


def init() -> None:
    with Session(engine) as session:
        init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
