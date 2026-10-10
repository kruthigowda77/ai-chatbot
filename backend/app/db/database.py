"""
database.py - Connects to the database and provides sessions.

A "session" is a short conversation with the database: you add, change,
or read rows, then commit (save) the changes.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

# SQLite needs one extra setting to work with FastAPI, which handles
# requests on multiple threads. Other databases don't need it.
connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

# The engine manages the actual connection to the database.
engine = create_engine(config.DATABASE_URL, connect_args=connect_args)

# A factory that creates new sessions.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every table class (model) inherits from this."""


def get_db() -> Iterator[Session]:
    """
    Give one request its own database session, and always close it afterwards.
    FastAPI will call this for each request that needs the database.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any tables that don't exist yet."""
    from app.db import models  # noqa: F401  (importing registers the table classes)

    Base.metadata.create_all(bind=engine)