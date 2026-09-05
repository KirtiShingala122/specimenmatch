"""
conftest.py — Shared pytest fixtures for the SpecimenMatch test suite.

Uses an in-memory SQLite database for test isolation so tests never
touch the development database file (specimenmatch.db).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.database import Base

# In-memory SQLite — isolated per test session
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory engine and build all tables once for the session."""
    from backend import models  # noqa: F401 — registers models on Base
    _engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture(scope="function")
def db(engine) -> Session:
    """
    Provide a clean database session for each test function.
    All changes are rolled back after the test to ensure isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
