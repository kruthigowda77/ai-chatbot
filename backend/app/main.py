"""
main.py - The FastAPI web server. Defines the API endpoints
and serves the frontend.

Run from the backend folder with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.schemas import ChatRequest, ChatResponse
from app.services.llm import get_ai_reply

# How many earlier messages to send to the AI with each request.
# Keeps requests fast and cheap. 20 messages = the last 10 back-and-forth exchanges.
MAX_HISTORY_MESSAGES = 20

# Create the web application.
app = FastAPI(
    title="AI Chatbot API",
    description="Backend for a full-stack AI chatbot.",
    version="0.2.0",
)


@app.get("/api/health")
def health_check():
    """Simple check that the server is running."""
    return {"status": "ok", "model": config.LLM_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Receive the user's new message plus earlier conversation history,
    and return the AI's reply.
    """
    # Keep only the most recent messages.
    recent_history = request.history[-MAX_HISTORY_MESSAGES:]

    # Convert each ChatMessage object into a plain dictionary,
    # e.g. {"role": "user", "content": "Hi"}
    messages = [msg.model_dump() for msg in recent_history]

    # Add the new message at the end.
    messages.append({"role": "user", "content": request.message})

    reply = get_ai_reply(messages)
    return ChatResponse(reply=reply)


# ===== Serve the frontend =====
# The frontend folder sits next to the backend folder.
# This MUST stay at the bottom of the file: routes are matched in order,
# so the /api endpoints above get the first chance to handle a request.
FRONTEND_DIR = config.BACKEND_DIR.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")