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

# Create the web application.
app = FastAPI(
    title="AI Chatbot API",
    description="Backend for a full-stack AI chatbot.",
    version="0.1.0",
)


@app.get("/api/health")
def health_check():
    """Simple check that the server is running."""
    return {"status": "ok", "model": config.LLM_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Receive one user message and return the AI's reply.
    (No memory yet: each message is answered on its own.)
    """
    messages = [{"role": "user", "content": request.message}]
    reply = get_ai_reply(messages)
    return ChatResponse(reply=reply)


# ===== Serve the frontend =====
# The frontend folder sits next to the backend folder.
# This MUST stay at the bottom of the file: routes are matched in order,
# so the /api endpoints above get the first chance to handle a request.
FRONTEND_DIR = config.BACKEND_DIR.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")