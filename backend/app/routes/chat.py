"""
routes/chat.py - Endpoints for chatting with the AI (logged-in users only).
Conversation history is loaded from and saved to the database.
Optionally, answers can use the user's uploaded documents (RAG).
"""

import logging
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.db.models import Conversation, User
from app.schemas import ChatRequest, ChatResponse, PersonalityOut
from app.services import chat_store, rag
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


@dataclass
class PreparedChat:
    """Everything needed to ask the AI, gathered in one place."""

    conversation: Conversation
    is_new: bool
    messages: list[dict]
    system_prompt: str
    sources_note: str  # added after the reply when documents were used ("" otherwise)


def prepare_chat(db: Session, request: ChatRequest, user: User) -> PreparedChat:
    """Find (or create) the conversation, load history, and search documents if asked."""
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
    system_prompt = personality.system_prompt
    sources_note = ""

    if request.use_documents:
        try:
            results = rag.search(db, user.id, request.message)
        except LLMServiceError:
            if is_new:
                chat_store.delete_conversation(db, conversation)
            raise
        system_prompt = rag.build_system_prompt(system_prompt, results)
        sources_note = rag.format_sources(results)

    messages = chat_store.load_recent_messages(db, conversation.id, MAX_HISTORY_MESSAGES)
    messages.append(dict(role="user", content=request.message))

    logger.info("User %s, conversation %s (%s): %d history messages, documents=%s",
                user.username, conversation.id, personality.id, len(messages) - 1,
                request.use_documents)
    return PreparedChat(conversation, is_new, messages, system_prompt, sources_note)


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the AI's complete reply in one JSON response."""
    prepared = prepare_chat(db, request, user)

    try:
        reply = get_ai_reply(prepared.messages, system_prompt=prepared.system_prompt)
    except LLMServiceError:
        if prepared.is_new:
            chat_store.delete_conversation(db, prepared.conversation)
        raise

    reply += prepared.sources_note
    chat_store.save_exchange(db, prepared.conversation.id, request.message, reply)
    return ChatResponse(reply=reply, conversation_id=prepared.conversation.id)


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream the AI's reply as plain text, then save it when it's complete."""
    prepared = prepare_chat(db, request, user)
    conversation_id = prepared.conversation.id

    try:
        pieces = stream_ai_reply(prepared.messages, system_prompt=prepared.system_prompt)
    except LLMServiceError:
        if prepared.is_new:
            chat_store.delete_conversation(db, prepared.conversation)
        raise

    def stream_and_save():
        received = []
        for piece in pieces:
            received.append(piece)
            yield piece

        reply = "".join(received)
        if reply.strip() and not reply.endswith(STREAM_INTERRUPTED_MESSAGE):
            if prepared.sources_note:
                yield prepared.sources_note  # show which pages were used
                reply += prepared.sources_note
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