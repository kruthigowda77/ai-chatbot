"""
chat_store.py - All database reads and writes for conversations and messages.

Keeping database code here (instead of inside the endpoints) means the
endpoints stay short, and this logic can be reused and tested on its own.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, utc_now

TITLE_MAX_LENGTH = 50


def make_title(first_message: str) -> str:
    """Turn the first message into a short title for the conversation."""
    text = " ".join(first_message.split())  # collapse extra spaces and line breaks
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[: TITLE_MAX_LENGTH - 3].rstrip() + "..."


def create_conversation(db: Session, first_message: str) -> Conversation:
    conversation = Conversation(title=make_title(first_message))
    db.add(conversation)
    db.commit()
    return conversation


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    """Return the conversation, or None if it doesn't exist."""
    return db.get(Conversation, conversation_id)


def list_conversations(db: Session) -> list[Conversation]:
    """All conversations, most recently active first."""
    statement = select(Conversation).order_by(Conversation.updated_at.desc())
    return list(db.scalars(statement))


def load_recent_messages(db: Session, conversation_id: str, limit: int) -> list[dict]:
    """
    The last `limit` messages of a conversation, oldest first,
    in the format the AI expects: [{"role": ..., "content": ...}, ...]
    """
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())  # newest first, so LIMIT keeps the most recent
        .limit(limit)
    )
    recent = list(db.scalars(statement))
    recent.reverse()  # back to oldest first
    return [{"role": m.role, "content": m.content} for m in recent]


def save_exchange(db: Session, conversation_id: str, user_text: str, reply: str) -> None:
    """Save one user message and the AI's reply, and mark the conversation as active."""
    db.add_all([
        Message(conversation_id=conversation_id, role="user", content=user_text),
        Message(conversation_id=conversation_id, role="assistant", content=reply),
    ])

    conversation = db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = utc_now()  # moves it to the top of the list

    db.commit()  # both messages are saved together, or neither is


def rename_conversation(db: Session, conversation: Conversation, title: str) -> Conversation:
    conversation.title = title.strip() or "New chat"
    db.commit()
    return conversation


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)  # its messages are deleted too (cascade)
    db.commit()