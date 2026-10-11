"""
routes/chat.py - Endpoints for chatting with the AI (logged-in users only).
Conversation history is loaded from and saved to the database.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.db.models import Conversation, User
from app.schemas import ChatRequest, ChatResponse, PersonalityOut
from app.services import chat_store
from app.services.auth import get_current_user
from app.services.llm import (
    STREAM_INTERRUPTED_MESSAGE,
    LLMServiceError,
    get_ai_reply,
    stream_ai_reply,
)
from app.services.personalities import (
    DEFAULT_PERSONALITY_ID,
    PERSONALITIES,
    Personality,
    get_personality,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_HISTORY_MESSAGES = 20


@router.get("/personalities", response_model=list[PersonalityOut])
def list_personalities():
    """The personalities users can choose from (without their system prompts)."""
    return [
        PersonalityOut(id=p.id, name=p.name, emoji=p.emoji, description=p.description)
        for p in PERSONALITIES.values()
    ]


def prepare_conversation(
    db: Session, request: ChatRequest, user: User
) -> tuple[Conversation, bool, list[dict], Personality]:
    """
    Find (or create) the user's conversation and build the message list for the AI.
    Returns: (conversation, is_new, messages, personality)
    """
    if request.conversation_id:
        conversation = chat_store.get_conversation(db, request.conversation_id, user.id)
        if conversation is None:
            raise HTTPException(
                status_code=404, detail="Conversation not found. Please start a new chat."
            )
        is_new = False
    else:
        personality_id = request.personality or DEFAULT_PERSONALITY_ID
        if personality_id not in PERSONALITIES:
            raise HTTPException(status_code=400, detail="Unknown personality.")
        conversation = chat_store.create_conversation(
            db, user.id, request.message, personality_id
        )
        is_new = True

    # A conversation always keeps the personality it was created with
    personality = get_personality(conversation.personality)

    messages = chat_store.load_recent_messages(db, conversation.id, MAX_HISTORY_MESSAGES)
    messages.append({"role": "user", "content": request.message})

    logger.info("User %s, conversation %s (%s): sending %d history messages",
                user.username, conversation.id, personality.id, len(messages) - 1)
    return conversation, is_new, messages, personality


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the AI's complete reply in one JSON response."""
    conversation, is_new, messages, personality = prepare_conversation(db, request, user)

    try:
        reply = get_ai_reply(messages, system_prompt=personality.system_prompt)
    except LLMServiceError:
        if is_new:
            chat_store.delete_conversation(db, conversation)
        raise

    chat_store.save_exchange(db, conversation.id, request.message, reply)
    return ChatResponse(reply=reply, conversation_id=conversation.id)


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream the AI's reply as plain text, then save it when it's complete."""
    conversation, is_new, messages, personality = prepare_conversation(db, request, user)
    conversation_id = conversation.id

    try:
        pieces = stream_ai_reply(messages, system_prompt=personality.system_prompt)
    except LLMServiceError:
        if is_new:
            chat_store.delete_conversation(db, conversation)
        raise

    def stream_and_save():
        received = []
        for piece in pieces:
            received.append(piece)
            yield piece

        reply = "".join(received)
        if reply.strip() and not reply.endswith(STREAM_INTERRUPTED_MESSAGE):
            with SessionLocal() as save_db:
                chat_store.save_exchange(save_db, conversation_id, request.message, reply)
        else:
            logger.warning("Conversation %s: reply incomplete, not saved", conversation_id)

    return StreamingResponse(
        stream_and_save(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Conversation-Id": conversation_id,
            "X-Accel-Buffering": "no",
        },
    )