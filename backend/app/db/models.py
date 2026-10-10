"""
models.py - The database tables, defined as Python classes.

Each class is a table. Each attribute is a column.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utc_now() -> datetime:
    """Current time in UTC. Servers store UTC; the browser converts to local time."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """A random, hard-to-guess ID like 'a3f9c2...' (32 characters)."""
    return uuid.uuid4().hex


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # One conversation has many messages.
    # cascade="all, delete-orphan": deleting a conversation also deletes its messages.
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)  # 1, 2, 3, ... assigned automatically
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))       # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)          # Text = no length limit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Each message belongs to one conversation.
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")