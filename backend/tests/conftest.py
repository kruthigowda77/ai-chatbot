"""
conftest.py - Shared test setup. pytest loads this automatically,
BEFORE the test files.
"""

import os
import tempfile
from pathlib import Path

# Point the app at a separate test database BEFORE any app code is imported,
# so tests never touch your real chatbot.db.
TEST_DB = Path(tempfile.gettempdir()) / "chatbot_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

import pytest  # noqa: E402

from app.db.database import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Give every test empty tables, and clean up afterwards."""
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)