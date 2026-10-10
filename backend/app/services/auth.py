"""
auth.py - Password hashing, login tokens, and finding the logged-in user.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db.database import get_db
from app.db.models import User

JWT_ALGORITHM = "HS256"

# Argon2 with recommended settings: salted, deliberately slow to resist guessing
password_hasher = PasswordHash.recommended()

# Used to keep login timing the same whether or not the username exists (see below)
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing")


# ===== Passwords =====

def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Return the user if the username and password are correct, otherwise None."""
    user = db.scalar(select(User).where(User.username == username.lower()))

    if user is None:
        # Still do a slow hash check, so attackers can't tell from the response
        # time whether a username exists.
        verify_password(password, DUMMY_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


# ===== Tokens =====

def create_access_token(user_id: int) -> str:
    """Create a signed token that says 'this is user X' until it expires."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expires_at}  # sub = subject (who it's about)
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user ID from a valid token, or None if it's invalid or expired."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


# ===== The logged-in user (used by protected endpoints) =====

# Reads the "Authorization: Bearer <token>" header. auto_error=False lets us
# return our own friendly message when it's missing.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: add `user: User = Depends(get_current_user)` to an endpoint
    and it will only run for logged-in users.
    """
    if credentials is None:
        raise _unauthorized("Please log in.")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthorized("Your session has expired. Please log in again.")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Your account was not found. Please log in again.")

    return user