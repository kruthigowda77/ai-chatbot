"""
chat_store.py - All database reads and writes for conversations and messages.

Every lookup includes the user's ID, so users can only ever reach their own chats.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, utc_now

TITLE_MAX_LENGTH = 50


def make_title(first_message: str) -> str:
    """Turn the first message into a short title for the conversation."""
    text = " ".join(first_message.split())
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[: TITLE_MAX_LENGTH - 3].rstrip() + "..."


def create_conversation(db: Session, user_id: int, first_message: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title=make_title(first_message))
    db.add(conversation)
    db.commit()
    return conversation


def get_conversation(db: Session, conversation_id: str, user_id: int) -> Conversation | None:
    """The conversation, only if it belongs to this user. Otherwise None."""
    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )
    return db.scalar(statement)


def list_conversations(db: Session, user_id: int) -> list[Conversation]:
    """This user's conversations, most recently active first."""
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(db.scalars(statement))


def load_recent_messages(db: Session, conversation_id: str, limit: int) -> list[dict]:
    """The last `limit` messages of a conversation, oldest first."""
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    recent = list(db.scalars(statement))
    recent.reverse()
    return [{"role": m.role, "content": m.content} for m in recent]


def save_exchange(db: Session, conversation_id: str, user_text: str, reply: str) -> None:
    """Save one user message and the AI's reply, and mark the conversation as active."""
    db.add_all([
        Message(conversation_id=conversation_id, role="user", content=user_text),
        Message(conversation_id=conversation_id, role="assistant", content=reply),
    ])

    conversation = db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = utc_now()

    db.commit()


def rename_conversation(db: Session, conversation: Conversation, title: str) -> Conversation:
    conversation.title = title.strip() or "New chat"
    db.commit()
    return conversation


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()