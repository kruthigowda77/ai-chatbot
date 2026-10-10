"""
main.py - The FastAPI web server. Defines the API endpoints
and serves the frontend.

Run from the backend folder with:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.schemas import ChatRequest, ChatResponse
from app.services.llm import LLMServiceError, get_ai_reply

# ===== Logging setup =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# How many earlier messages to send to the AI with each request.
MAX_HISTORY_MESSAGES = 20

app = FastAPI(
    title="AI Chatbot API",
    description="Backend for a full-stack AI chatbot.",
    version="0.3.0",
)


# ===== Error handlers =====

@app.exception_handler(LLMServiceError)
async def handle_llm_error(request: Request, exc: LLMServiceError):
    """Turn AI service problems into a clean JSON response with a friendly message."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.user_message})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    """Safety net for any bug we didn't anticipate. Never show internals to the user."""
    logger.exception("Unexpected error while handling %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something unexpected went wrong on the server. Please try again."},
    )


# ===== Endpoints =====

@app.get("/api/health")
def health_check():
    """Simple check that the server is running."""
    return {"status": "ok", "model": config.LLM_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Receive the new message plus earlier history, and return the AI's reply."""
    recent_history = request.history[-MAX_HISTORY_MESSAGES:]
    messages = [msg.model_dump() for msg in recent_history]
    messages.append({"role": "user", "content": request.message})

    logger.info("Chat request with %d history messages", len(recent_history))

    reply = get_ai_reply(messages)  # may raise LLMServiceError, handled above
    return ChatResponse(reply=reply)


# ===== Serve the frontend (must stay at the bottom) =====
FRONTEND_DIR = config.BACKEND_DIR.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")