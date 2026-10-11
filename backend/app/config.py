"""
config.py - Loads all settings for the backend from the .env file.

Every other file imports settings from here, so if we ever change
how settings are loaded, we only change this one file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> backend/app -> backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

# Read the .env file and load its values as environment variables.
load_dotenv(ENV_FILE)


# ===== AI model =====
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None  # empty text becomes None

# The model that turns text into embeddings (lists of numbers) for document search
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

# Fail fast: stop immediately with a helpful message if the key is missing.
PLACEHOLDER_KEYS = {"your-api-key-here", "sk-proj-paste-your-real-key-here"}
if not LLM_API_KEY or LLM_API_KEY in PLACEHOLDER_KEYS:
    raise RuntimeError(
        f"LLM_API_KEY is missing. Make sure the file {ENV_FILE} exists "
        "and contains your real key, like: LLM_API_KEY=AIza... (Gemini) or sk-proj-... (OpenAI)"
    )


def masked_key() -> str:
    """Return a safe version of the key for printing, e.g. 'AIzaSyB...a1b2'."""
    return f"{LLM_API_KEY[:7]}...{LLM_API_KEY[-4:]}"


# ===== Database =====
# Defaults to a SQLite file inside the backend folder.
# Later, for MySQL/PostgreSQL, set DATABASE_URL in .env instead.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BACKEND_DIR / 'chatbot.db').as_posix()}",
)


# ===== Login security =====
# Signs login tokens. Must be long and random, and never shared.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or too short. Generate one with:\n"
        '  python -c "import secrets; print(secrets.token_hex(32))"\n'
        f"and add it to {ENV_FILE} as JWT_SECRET_KEY=..."
    )

# How long a login lasts before the user must log in again (default: 24 hours)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


# ===== Document uploads =====
# The largest file a user may upload, in megabytes
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))