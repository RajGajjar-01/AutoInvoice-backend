import structlog
from sqlmodel import Session, select

from app.core.db import engine

logger = structlog.get_logger(__name__)


def init() -> None:
    with Session(engine) as session:
        session.exec(select(1))


def main() -> None:
    logger.info("Initializing service")
    init()
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
