"""
test_api.py - Automated tests for the chatbot API.

The real AI is replaced with a fake one, and a separate test database is
used (see conftest.py), so tests are fast, free, and repeatable.

Run from the backend folder with:
    python -m pytest -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import main
from app.db.database import SessionLocal
from app.db.models import User
from app.routes import chat as chat_routes
from app.services import chat_store
from app.services.llm import LLMServiceError
from app.services.personalities import PERSONALITIES

client = TestClient(main.app)

FAKE_REPLY = "Hello from the fake AI!"
PASSWORD = "password123"


# ===== Helpers and fixtures =====

def register(username="kruthi", password=PASSWORD):
    """Create an account and return the headers needed to act as that user."""
    response = client.post("/api/auth/register", json=dict(username=username, password=password))
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return dict(Authorization="Bearer " + token)


@pytest.fixture
def auth_headers():
    return register()


@pytest.fixture
def fake_ai(monkeypatch):
    """Replace the real AI with a fake that records what it receives."""
    calls = []

    def fake_get_ai_reply(messages, system_prompt=None):
        calls.append(messages)
        return FAKE_REPLY

    monkeypatch.setattr(chat_routes, "get_ai_reply", fake_get_ai_reply)
    return calls


def simplify(messages):
    return [(m["role"], m["content"]) for m in messages]


def msg(role, content):
    return dict(role=role, content=content)


# ===== Public endpoints =====

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Assistant" in response.text


# ===== Accounts =====

def test_register_returns_token_and_me_works():
    headers = register("kruthi")

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json() == dict(username="kruthi")


def test_password_is_stored_hashed():
    register("kruthi", PASSWORD)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "kruthi"))

    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")


def test_duplicate_username_is_rejected():
    register("kruthi")
    response = client.post("/api/auth/register", json=dict(username="Kruthi", password=PASSWORD))
    assert response.status_code == 409


def test_login_with_correct_and_wrong_password():
    register("kruthi", PASSWORD)

    good = client.post("/api/auth/login", json=dict(username="kruthi", password=PASSWORD))
    bad = client.post("/api/auth/login", json=dict(username="kruthi", password="wrong-password"))
    unknown = client.post("/api/auth/login", json=dict(username="nobody", password=PASSWORD))

    assert good.status_code == 200
    assert "access_token" in good.json()
    assert bad.status_code == 401
    assert unknown.status_code == 401
    assert bad.json() == unknown.json()


def test_endpoints_require_login():
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/chat", json=dict(message="Hi")).status_code == 401

    fake_token = dict(Authorization="Bearer not-a-real-token")
    assert client.get("/api/conversations", headers=fake_token).status_code == 401


def test_users_cannot_see_each_others_chats(fake_ai):
    kruthi = register("kruthi")
    other = register("someone_else")

    convo_id = client.post(
        "/api/chat", json=dict(message="My secret"), headers=kruthi
    ).json()["conversation_id"]
    convo_url = "/api/conversations/" + convo_id

    assert client.get("/api/conversations", headers=other).json() == []
    assert client.get(convo_url, headers=other).status_code == 404
    assert client.post(
        "/api/chat", json=dict(message="Hi", conversation_id=convo_id), headers=other
    ).status_code == 404
    assert client.patch(convo_url, json=dict(title="Hacked"), headers=other).status_code == 404
    assert client.delete(convo_url, headers=other).status_code == 404

    mine = client.get(convo_url, headers=kruthi).json()
    assert mine["title"] == "My secret"


# ===== Saving and loading conversations =====

def test_new_chat_creates_and_saves_conversation(fake_ai, auth_headers):
    response = client.post("/api/chat", json=dict(message="My name is Kruthi"), headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == FAKE_REPLY

    saved = client.get("/api/conversations/" + data["conversation_id"], headers=auth_headers).json()
    assert saved["title"] == "My name is Kruthi"
    assert simplify(saved["messages"]) == [
        ("user", "My name is Kruthi"),
        ("assistant", FAKE_REPLY),
    ]


def test_follow_up_uses_saved_history(fake_ai, auth_headers):
    first = client.post(
        "/api/chat", json=dict(message="My name is Kruthi"), headers=auth_headers
    ).json()

    client.post(
        "/api/chat",
        json=dict(message="What is my name?", conversation_id=first["conversation_id"]),
        headers=auth_headers,
    )

    assert fake_ai[1] == [
        msg("user", "My name is Kruthi"),
        msg("assistant", FAKE_REPLY),
        msg("user", "What is my name?"),
    ]


def test_long_history_is_trimmed(fake_ai, auth_headers):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "kruthi"))
        conversation = chat_store.create_conversation(db, user.id, "Long chat")
        for i in range(15):
            chat_store.save_exchange(db, conversation.id, "question " + str(i), "answer " + str(i))
        conversation_id = conversation.id

    client.post(
        "/api/chat",
        json=dict(message="latest", conversation_id=conversation_id),
        headers=auth_headers,
    )

    sent = fake_ai[0]
    assert len(sent) == chat_routes.MAX_HISTORY_MESSAGES + 1
    assert sent[0]["content"] == "question 5"
    assert sent[-1]["content"] == "latest"


def test_unknown_conversation_returns_404(fake_ai, auth_headers):
    response = client.post(
        "/api/chat", json=dict(message="Hi", conversation_id="0" * 32), headers=auth_headers
    )
    assert response.status_code == 404


# ===== Input validation =====

def test_invalid_conversation_id_is_rejected(auth_headers):
    response = client.post(
        "/api/chat", json=dict(message="Hi", conversation_id="../../secret"), headers=auth_headers
    )
    assert response.status_code == 422


def test_empty_message_is_rejected(auth_headers):
    response = client.post("/api/chat", json=dict(message=""), headers=auth_headers)
    assert response.status_code == 422


def test_too_long_message_is_rejected(auth_headers):
    response = client.post("/api/chat", json=dict(message="a" * 4001), headers=auth_headers)
    assert response.status_code == 422


# ===== Error handling =====

def test_ai_error_returns_friendly_message(monkeypatch, auth_headers):
    def failing_ai(messages, system_prompt=None):
        raise LLMServiceError("The AI service is busy right now.", 503)

    monkeypatch.setattr(chat_routes, "get_ai_reply", failing_ai)

    response = client.post("/api/chat", json=dict(message="Hi"), headers=auth_headers)

    assert response.status_code == 503
    assert response.json() == dict(detail="The AI service is busy right now.")
    assert client.get("/api/conversations", headers=auth_headers).json() == []


def test_unexpected_error_hides_details(monkeypatch, auth_headers):
    def crashing_ai(messages, system_prompt=None):
        raise ValueError("secret internal detail")

    monkeypatch.setattr(chat_routes, "get_ai_reply", crashing_ai)

    safe_client = TestClient(main.app, raise_server_exceptions=False)
    response = safe_client.post("/api/chat", json=dict(message="Hi"), headers=auth_headers)

    assert response.status_code == 500
    assert "secret internal detail" not in response.text


# ===== Streaming =====

def test_stream_sends_pieces_and_saves_reply(monkeypatch, auth_headers):
    def fake_stream(messages, system_prompt=None):
        return iter(["Hel", "lo ", "Kruthi!"])

    monkeypatch.setattr(chat_routes, "stream_ai_reply", fake_stream)

    response = client.post("/api/chat/stream", json=dict(message="Hi"), headers=auth_headers)

    assert response.status_code == 200
    assert response.text == "Hello Kruthi!"

    conversation_id = response.headers["X-Conversation-Id"]
    saved = client.get("/api/conversations/" + conversation_id, headers=auth_headers).json()
    assert simplify(saved["messages"]) == [("user", "Hi"), ("assistant", "Hello Kruthi!")]


def test_stream_error_before_start_returns_friendly_message(monkeypatch, auth_headers):
    def failing_stream(messages, system_prompt=None):
        raise LLMServiceError("The AI service is busy right now.", 503)

    monkeypatch.setattr(chat_routes, "stream_ai_reply", failing_stream)

    response = client.post("/api/chat/stream", json=dict(message="Hi"), headers=auth_headers)

    assert response.status_code == 503
    assert response.json() == dict(detail="The AI service is busy right now.")


# ===== Managing conversations =====

def test_list_rename_and_delete_conversations(fake_ai, auth_headers):
    first_id = client.post(
        "/api/chat", json=dict(message="First chat"), headers=auth_headers
    ).json()["conversation_id"]
    client.post("/api/chat", json=dict(message="Second chat"), headers=auth_headers)
    first_url = "/api/conversations/" + first_id

    listed = client.get("/api/conversations", headers=auth_headers).json()
    titles = set(c["title"] for c in listed)
    assert titles == set(["First chat", "Second chat"])

    renamed = client.patch(first_url, json=dict(title="Renamed"), headers=auth_headers)
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"

    assert client.delete(first_url, headers=auth_headers).status_code == 204
    assert client.get(first_url, headers=auth_headers).status_code == 404


def test_timestamps_include_timezone(fake_ai, auth_headers):
    client.post("/api/chat", json=dict(message="Hi"), headers=auth_headers)

    updated_at = client.get("/api/conversations", headers=auth_headers).json()[0]["updated_at"]

    assert updated_at.endswith("Z") or updated_at.endswith("+00:00")


# ===== Personalities =====

def test_personalities_are_listed_without_prompts():
    data = client.get("/api/chat/personalities").json()

    ids = set(p["id"] for p in data)
    expected = set(["assistant", "coding_tutor", "interview_coach", "simple_explainer"])
    assert expected <= ids
    assert all("system_prompt" not in p for p in data)


def test_chat_uses_the_chosen_personality(monkeypatch, auth_headers):
    prompts_received = []

    def recording_ai(messages, system_prompt=None):
        prompts_received.append(system_prompt)
        return FAKE_REPLY

    monkeypatch.setattr(chat_routes, "get_ai_reply", recording_ai)

    first = client.post(
        "/api/chat",
        json=dict(message="Help me with loops", personality="coding_tutor"),
        headers=auth_headers,
    ).json()

    # A follow-up that asks for a different personality still uses the original one
    client.post(
        "/api/chat",
        json=dict(
            message="More please",
            conversation_id=first["conversation_id"],
            personality="interview_coach",
        ),
        headers=auth_headers,
    )

    tutor_prompt = PERSONALITIES["coding_tutor"].system_prompt
    assert prompts_received == [tutor_prompt, tutor_prompt]

    summary = client.get("/api/conversations", headers=auth_headers).json()[0]
    assert summary["personality"] == "coding_tutor"


def test_unknown_personality_is_rejected(fake_ai, auth_headers):
    response = client.post(
        "/api/chat", json=dict(message="Hi", personality="evil_bot"), headers=auth_headers
    )
    assert response.status_code == 400