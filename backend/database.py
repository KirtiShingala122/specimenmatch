"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.

All models import Base from here; the application calls init_db() on startup
to ensure all tables exist (create_all strategy — suitable for hackathon MVP).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./specimenmatch.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
    echo=False,  # Set True for SQL query logging during dev
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    __allow_unmapped__ = True lets SQLAlchemy 2 coexist with plain Python
    type annotations on Column() attributes (classic mapping style).
    Without this, SQLAlchemy 2 tries to interpret every annotated attribute
    as a Mapped[] declaration and raises ArgumentError on relationship hints.
    """
    __allow_unmapped__ = True


def init_db() -> None:
    """
    Create all tables defined on Base.metadata if they do not already exist.
    Called once at application startup (or during tests).
    """
    # Import all models here so their table definitions are registered on Base
    from backend import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that yields a per-request database session and
    guarantees the session is closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
