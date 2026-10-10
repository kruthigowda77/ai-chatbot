"""
main.py - Creates the FastAPI app: logging, startup, error handlers,
routers, and serving the frontend.

Run from the backend folder with:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.db.database import init_db
from app.routes import auth, chat, conversations
from app.services.llm import LLMServiceError

# ===== Logging setup =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ===== Startup =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs when the server starts (before yield) and stops (after yield)."""
    init_db()
    logger.info("Database ready at %s", config.DATABASE_URL)
    yield


app = FastAPI(
    title="AI Chatbot API",
    description="Backend for a full-stack AI chatbot.",
    version="0.7.0",
    lifespan=lifespan,
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


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)


# ===== Serve the frontend (must stay at the bottom) =====
FRONTEND_DIR = config.BACKEND_DIR.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")