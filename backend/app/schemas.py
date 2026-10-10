"""
schemas.py - Defines the shape of data going in and out of our API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
        pattern=r"^[0-9a-f]{32}$",  # must look like one of our IDs, nothing else
        description="Leave empty to start a new conversation",
    )


class ChatResponse(BaseModel):
    """What POST /api/chat sends back."""

    reply: str
    conversation_id: str


class MessageOut(BaseModel):
    """One saved message, as sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)  # can be built from a database object

    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    """A conversation in the list (no messages, to keep the list small)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    """One conversation with all its messages."""

    messages: list[MessageOut]


class ConversationRename(BaseModel):
    """Body for renaming a conversation."""

    title: str = Field(..., min_length=1, max_length=200)