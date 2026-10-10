"""
routes/conversations.py - List, open, rename, and delete saved conversations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation
from app.schemas import ConversationDetail, ConversationRename, ConversationSummary
from app.services import chat_store

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_or_404(db: Session, conversation_id: str) -> Conversation:
    conversation = chat_store.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    """All conversations, most recent first."""
    return chat_store.list_conversations(db)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """One conversation with all its messages."""
    return get_conversation_or_404(db, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str, body: ConversationRename, db: Session = Depends(get_db)
):
    """Change a conversation's title."""
    conversation = get_conversation_or_404(db, conversation_id)
    return chat_store.rename_conversation(db, conversation, body.title)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages."""
    conversation = get_conversation_or_404(db, conversation_id)
    chat_store.delete_conversation(db, conversation)