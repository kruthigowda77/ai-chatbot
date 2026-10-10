"""
routes/conversations.py - List, open, rename, and delete the logged-in user's conversations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation, User
from app.schemas import ConversationDetail, ConversationRename, ConversationSummary
from app.services import chat_store
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_or_404(db: Session, conversation_id: str, user: User) -> Conversation:
    conversation = chat_store.get_conversation(db, conversation_id, user.id)
    if conversation is None:
        # 404, not 403: don't even reveal that someone else's chat exists
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Your conversations, most recent first."""
    return chat_store.list_conversations(db, user.id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """One of your conversations, with all its messages."""
    return get_conversation_or_404(db, conversation_id, user)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str,
    body: ConversationRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change the title of one of your conversations."""
    conversation = get_conversation_or_404(db, conversation_id, user)
    return chat_store.rename_conversation(db, conversation, body.title)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Delete one of your conversations and all its messages."""
    conversation = get_conversation_or_404(db, conversation_id, user)
    chat_store.delete_conversation(db, conversation)