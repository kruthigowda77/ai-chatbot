"""
test_api.py - Automated tests for the chatbot API.

The real AI is replaced with a fake one, and a separate test database
is used (see conftest.py), so tests are fast, free, and repeatable.

Run from the backend folder with:
    python -m pytest -v
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db.database import SessionLocal
from app.routes import chat as chat_routes
from app.services import chat_store
from app.services.llm import LLMServiceError

client = TestClient(main.app)

FAKE_REPLY = "Hello from the fake AI!"


@pytest.fixture
def fake_ai(monkeypatch):
    """Replace the real AI with a fake that records what it receives."""
    calls = []

    def fake_get_ai_reply(messages):
        calls.append(messages)
        return FAKE_REPLY

    monkeypatch.setattr(chat_routes, "get_ai_reply", fake_get_ai_reply)
    return calls


def simplify(messages):
    """Keep just role and content, to make comparisons easy."""
    return [(m["role"], m["content"]) for m in messages]


# ===== Basic endpoints =====

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Assistant" in response.text


# ===== Saving and loading conversations =====

def test_new_chat_creates_and_saves_conversation(fake_ai):
    response = client.post("/api/chat", json={"message": "My name is Kruthi"})

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == FAKE_REPLY

    saved = client.get(f"/api/conversations/{data['conversation_id']}").json()
    assert saved["title"] == "My name is Kruthi"
    assert simplify(saved["messages"]) == [
        ("user", "My name is Kruthi"),
        ("assistant", FAKE_REPLY),
    ]


def test_follow_up_uses_saved_history(fake_ai):
    first = client.post("/api/chat", json={"message": "My name is Kruthi"}).json()

    client.post(
        "/api/chat",
        json={"message": "What is my name?", "conversation_id": first["conversation_id"]},
    )

    # The second AI call must include the saved history, then the new message
    assert fake_ai[1] == [
        {"role": "user", "content": "My name is Kruthi"},
        {"role": "assistant", "content": FAKE_REPLY},
        {"role": "user", "content": "What is my name?"},
    ]


def test_long_history_is_trimmed(fake_ai):
    # Prepare a conversation with 30 saved messages (15 exchanges)
    with SessionLocal() as db:
        conversation = chat_store.create_conversation(db, "Long chat")
        for i in range(15):
            chat_store.save_exchange(db, conversation.id, f"question {i}", f"answer {i}")
        conversation_id = conversation.id

    client.post("/api/chat", json={"message": "latest", "conversation_id": conversation_id})

    sent = fake_ai[0]
    assert len(sent) == chat_routes.MAX_HISTORY_MESSAGES + 1
    assert sent[0]["content"] == "question 5"  # oldest kept message
    assert sent[-1]["content"] == "latest"     # new message is last


def test_unknown_conversation_returns_404(fake_ai):
    response = client.post(
        "/api/chat", json={"message": "Hi", "conversation_id": "0" * 32}
    )
    assert response.status_code == 404


# ===== Input validation =====

def test_invalid_conversation_id_is_rejected():
    response = client.post(
        "/api/chat", json={"message": "Hi", "conversation_id": "../../secret"}
    )
    assert response.status_code == 422


def test_empty_message_is_rejected():
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_too_long_message_is_rejected():
    response = client.post("/api/chat", json={"message": "a" * 4001})
    assert response.status_code == 422


# ===== Error handling =====

def test_ai_error_returns_friendly_message(monkeypatch):
    def failing_ai(messages):
        raise LLMServiceError("The AI service is busy right now.", 503)

    monkeypatch.setattr(chat_routes, "get_ai_reply", failing_ai)

    response = client.post("/api/chat", json={"message": "Hi"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI service is busy right now."}
    # A failed first message must not leave an empty conversation behind
    assert client.get("/api/conversations").json() == []


def test_unexpected_error_hides_details(monkeypatch):
    def crashing_ai(messages):
        raise ValueError("secret internal detail")

    monkeypatch.setattr(chat_routes, "get_ai_reply", crashing_ai)

    safe_client = TestClient(main.app, raise_server_exceptions=False)
    response = safe_client.post("/api/chat", json={"message": "Hi"})

    assert response.status_code == 500
    assert "secret internal detail" not in response.text


# ===== Streaming =====

def test_stream_sends_pieces_and_saves_reply(monkeypatch):
    monkeypatch.setattr(
        chat_routes, "stream_ai_reply", lambda messages: iter(["Hel", "lo ", "Kruthi!"])
    )

    response = client.post("/api/chat/stream", json={"message": "Hi"})

    assert response.status_code == 200
    assert response.text == "Hello Kruthi!"

    conversation_id = response.headers["X-Conversation-Id"]
    saved = client.get(f"/api/conversations/{conversation_id}").json()
    assert simplify(saved["messages"]) == [("user", "Hi"), ("assistant", "Hello Kruthi!")]


def test_stream_error_before_start_returns_friendly_message(monkeypatch):
    def failing_stream(messages):
        raise LLMServiceError("The AI service is busy right now.", 503)

    monkeypatch.setattr(chat_routes, "stream_ai_reply", failing_stream)

    response = client.post("/api/chat/stream", json={"message": "Hi"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI service is busy right now."}


# ===== Managing conversations =====

def test_list_rename_and_delete_conversations(fake_ai):
    first_id = client.post("/api/chat", json={"message": "First chat"}).json()["conversation_id"]
    client.post("/api/chat", json={"message": "Second chat"})

    titles = {c["title"] for c in client.get("/api/conversations").json()}
    assert titles == {"First chat", "Second chat"}

    renamed = client.patch(f"/api/conversations/{first_id}", json={"title": "Renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"

    assert client.delete(f"/api/conversations/{first_id}").status_code == 204
    assert client.get(f"/api/conversations/{first_id}").status_code == 404
    
    

def test_timestamps_include_timezone(fake_ai):
    client.post("/api/chat", json={"message": "Hi"})

    updated_at = client.get("/api/conversations").json()[0]["updated_at"]

    # "Z" or "+00:00" both mean UTC; without one, browsers would guess wrong
    assert updated_at.endswith("Z") or updated_at.endswith("+00:00")