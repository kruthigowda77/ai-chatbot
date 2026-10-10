"""
conftest.py - Shared test setup. pytest loads this automatically,
BEFORE the test files.
"""

import os
import tempfile
from pathlib import Path

# Test settings, set BEFORE any app code is imported. These take priority over
# .env, so tests never use your real database or your real API key.
TEST_DB = Path(tempfile.gettempdir()) / "chatbot_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["LLM_API_KEY"] = "test-key-not-real"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"

import pytest  # noqa: E402

from app.db.database import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Give every test brand-new, empty tables, and clean up afterwards."""
    Base.metadata.drop_all(bind=engine)  # remove leftovers from older test runs
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)