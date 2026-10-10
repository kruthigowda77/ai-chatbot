"""
config.py - Loads all settings for the backend from the .env file.

Every other file imports settings from here, so if we ever change
how settings are loaded, we only change this one file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build the path to backend/.env, no matter where the program is started from.
# __file__ is this file (backend/app/config.py).
# .parent is backend/app, and .parent again is backend.
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

# Read the .env file and load its values as environment variables.
load_dotenv(ENV_FILE)

# Read each setting. os.getenv returns None if the setting is missing,
# or the default value if we provide one.
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.4-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None  # empty text becomes None

# Fail fast: stop immediately with a helpful message if the key is missing.
if not LLM_API_KEY or LLM_API_KEY == "your-api-key-here":
    raise RuntimeError(
        f"LLM_API_KEY is missing. Make sure the file {ENV_FILE} exists "
         "and contains your real key, like: LLM_API_KEY=AIza... (Gemini) or sk-proj-... (OpenAI)"
    )


def masked_key() -> str:
    """Return a safe version of the key for printing, e.g. 'sk-proj...a1b2'."""
    return f"{LLM_API_KEY[:7]}...{LLM_API_KEY[-4:]}"