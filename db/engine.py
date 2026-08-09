"""SQLAlchemy engine and session factory for the workout-log database."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = os.environ.get("WORKOUT_LOG_DB", str(_DB_DIR / "workout_log.db"))

DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a scoped session (usable as a FastAPI dependency)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
