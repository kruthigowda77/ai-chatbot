"""
routes/chat.py - Endpoints for chatting with the AI.
Conversation history is loaded from and saved to the database.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.db.models import Conversation
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_store
from app.services.llm import (
    STREAM_INTERRUPTED_MESSAGE,
    LLMServiceError,
    get_ai_reply,
    stream_ai_reply,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# How many earlier messages to send to the AI with each request.
MAX_HISTORY_MESSAGES = 20


def prepare_conversation(
    db: Session, request: ChatRequest
) -> tuple[Conversation, bool, list[dict]]:
    """
    Find (or create) the conversation and build the message list for the AI.
    Returns: (conversation, is_new, messages)
    """
    if request.conversation_id:
        conversation = chat_store.get_conversation(db, request.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=404, detail="Conversation not found. Please start a new chat."
            )
        is_new = False
    else:
        conversation = chat_store.create_conversation(db, request.message)
        is_new = True

    messages = chat_store.load_recent_messages(db, conversation.id, MAX_HISTORY_MESSAGES)
    messages.append({"role": "user", "content": request.message})

    logger.info("Conversation %s: sending %d history messages",
                conversation.id, len(messages) - 1)
    return conversation, is_new, messages


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Return the AI's complete reply in one JSON response."""
    conversation, is_new, messages = prepare_conversation(db, request)

    try:
        reply = get_ai_reply(messages)
    except LLMServiceError:
        # Don't leave an empty conversation behind if the very first message failed
        if is_new:
            chat_store.delete_conversation(db, conversation)
        raise

    chat_store.save_exchange(db, conversation.id, request.message, reply)
    return ChatResponse(reply=reply, conversation_id=conversation.id)


@router.post("/stream")
def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """Stream the AI's reply as plain text, then save it when it's complete."""
    conversation, is_new, messages = prepare_conversation(db, request)
    conversation_id = conversation.id

    try:
        pieces = stream_ai_reply(messages)
    except LLMServiceError:
        if is_new:
            chat_store.delete_conversation(db, conversation)
        raise

    def stream_and_save():
        received = []
        for piece in pieces:
            received.append(piece)
            yield piece  # send each piece to the browser right away

        # Streaming finished: save the exchange if the reply is complete.
        reply = "".join(received)
        if reply.strip() and not reply.endswith(STREAM_INTERRUPTED_MESSAGE):
            # This runs after the endpoint has returned, so it uses its own session.
            with SessionLocal() as save_db:
                chat_store.save_exchange(save_db, conversation_id, request.message, reply)
        else:
            logger.warning("Conversation %s: reply incomplete, not saved", conversation_id)

    return StreamingResponse(
        stream_and_save(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Conversation-Id": conversation_id,  # tells the browser which chat this is
            "X-Accel-Buffering": "no",
        },
    )