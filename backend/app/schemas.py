"""
schemas.py - Defines the shape of data going in and out of our API.
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def ensure_utc(value: datetime) -> datetime:
    """
    All our times are saved in UTC, but SQLite forgets the timezone.
    Mark times without a timezone as UTC, so browsers convert them correctly.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# A datetime that is always sent out with its UTC timezone attached
UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]


# ===== Chat =====

class ChatRequest(BaseModel):
    """What the frontend sends to POST /api/chat and /api/chat/stream."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The user's new chat message",
        examples=["Hello! What can you do?"],
    )
    conversation_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{32}$",
        description="Leave empty to start a new conversation",
    )
    personality: str | None = Field(
        default=None,
        max_length=30,
        description="Personality ID for a NEW conversation (ignored for existing ones)",
    )


class ChatResponse(BaseModel):
    """What POST /api/chat sends back."""

    reply: str
    conversation_id: str


# ===== Conversations =====

class MessageOut(BaseModel):
    """One saved message, as sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: UtcDatetime


class ConversationSummary(BaseModel):
    """A conversation in the list (no messages, to keep the list small)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    personality: str
    updated_at: UtcDatetime


class ConversationDetail(ConversationSummary):
    """One conversation with all its messages."""

    messages: list[MessageOut]


class ConversationRename(BaseModel):
    """Body for renaming a conversation."""

    title: str = Field(..., min_length=1, max_length=200)


# ===== Accounts =====

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"  # letters, numbers, underscore, dot, hyphen


class AuthRequest(BaseModel):
    """Body for register and login."""

    username: str = Field(..., min_length=3, max_length=30, pattern=USERNAME_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Sent back after a successful register or login."""

    access_token: str
    token_type: str = "bearer"
    username: str


class UserOut(BaseModel):
    """Public information about a user (never the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    username: str


# ===== Personalities =====

class PersonalityOut(BaseModel):
    """A personality as shown to users. The system prompt is NOT included."""

    id: str
    name: str
    emoji: str
    description: str