"""
routes/auth.py - Sign up, log in, and check who is logged in.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.schemas import AuthRequest, TokenResponse, UserOut
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: AuthRequest, db: Session = Depends(get_db)):
    """Create an account and log in straight away."""
    username = body.username.lower()  # "Kruthi" and "kruthi" are the same account

    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="That username is already taken.")

    user = User(username=username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two people registered the same name at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail="That username is already taken.")

    logger.info("New user registered: %s", username)
    return TokenResponse(access_token=create_access_token(user.id), username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(body: AuthRequest, db: Session = Depends(get_db)):
    """Check the username and password, and return a token."""
    user = authenticate_user(db, body.username, body.password)
    if user is None:
        # Same message for "no such user" and "wrong password" (don't help attackers)
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    return TokenResponse(access_token=create_access_token(user.id), username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Return the logged-in user. Used by the frontend to check a saved token."""
    return user