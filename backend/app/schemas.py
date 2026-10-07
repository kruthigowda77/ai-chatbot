"""
schemas.py - Defines the shape of data going in and out of our API.

FastAPI uses these classes (built with Pydantic) to automatically:
- validate incoming requests (reject bad data with a 422 error)
- generate the interactive docs page at /docs
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """What the frontend sends to POST /api/chat."""

    message: str = Field(
        ...,                      # "..." means this field is required
        min_length=1,             # reject empty messages
        max_length=4000,          # reject huge messages (protects your credits)
        description="The user's chat message",
        examples=["Hello! What can you do?"],
    )


class ChatResponse(BaseModel):
    """What POST /api/chat sends back to the frontend."""

    reply: str = Field(..., description="The AI's response")