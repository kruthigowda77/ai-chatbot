"""
schemas.py - Defines the shape of data going in and out of our API.

FastAPI uses these classes (built with Pydantic) to automatically:
- validate incoming requests (reject bad data with a 422 error)
- generate the interactive docs page at /docs
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One earlier message in the conversation."""

    # Only "user" and "assistant" are allowed. A "system" role is rejected,
    # so nobody can override the bot's instructions from the browser.
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    """What the frontend sends to POST /api/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The user's new chat message",
        examples=["Hello! What can you do?"],
    )
    history: list[ChatMessage] = Field(
        default_factory=list,   # if no history is sent, use an empty list
        max_length=100,         # hard safety limit on how much can be sent
        description="Earlier messages in this conversation, oldest first",
    )


class ChatResponse(BaseModel):
    """What POST /api/chat sends back to the frontend."""

    reply: str = Field(..., description="The AI's response")