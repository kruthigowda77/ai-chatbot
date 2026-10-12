"""
test_rag.py - Tests for answering questions from the user's documents.

Embeddings are faked with simple "topic" vectors, so we know exactly which
chunks should match which questions, and no real AI is ever called.
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.routes import chat as chat_routes
from app.services import documents, rag

client = TestClient(main.app)

PASSWORD = "password123"


def topic_vector(text):
    """A fake 3-number embedding: [about Python?, about food?, small constant]."""
    lower = text.lower()
    return [
        1.0 if "python" in lower else 0.0,
        1.0 if "dosa" in lower else 0.0,
        0.01,
    ]


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(documents, "embed_texts", lambda texts: [topic_vector(t) for t in texts])


@pytest.fixture
def ai_calls(monkeypatch):
    """A fake AI that records the system prompt it receives."""
    calls = []

    def fake_ai(messages, system_prompt=None):
        calls.append(system_prompt)
        return "Fake answer."

    monkeypatch.setattr(chat_routes, "get_ai_reply", fake_ai)
    return calls


def register(username="kruthi"):
    response = client.post("/api/auth/register", json=dict(username=username, password=PASSWORD))
    return dict(Authorization="Bearer " + response.json()["access_token"])


def upload(headers, filename, text):
    response = client.post(
        "/api/documents",
        files=dict(file=(filename, text.encode("utf-8"), "text/plain")),
        headers=headers,
    )
    assert response.status_code == 201, response.text


# ===== Pure functions =====

def test_cosine_similarity():
    assert rag.cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert rag.cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert rag.cosine_similarity([0, 0], [1, 1]) == 0.0  # no crash on empty vectors


def test_format_sources_groups_pages_by_file():
    results = [
        rag.SearchResult(0.9, "notes.pdf", 5, "a"),
        rag.SearchResult(0.8, "notes.pdf", 3, "b"),
        rag.SearchResult(0.7, "notes.pdf", 5, "c"),
        rag.SearchResult(0.6, "cv.pdf", 1, "d"),
    ]
    assert rag.format_sources(results) == "\n\n---\n📄 **Sources:** notes.pdf (p. 3, 5); cv.pdf (p. 1)"
    assert rag.format_sources([]) == ""


# ===== Using documents in chat =====

def test_question_uses_the_most_relevant_document(ai_calls):
    headers = register()
    upload(headers, "food.txt", "Masala dosa is a South Indian breakfast.")
    upload(headers, "skills.txt", "Kruthi writes Python and builds APIs.")

    response = client.post(
        "/api/chat",
        json=dict(message="Does she know Python?", use_documents=True),
        headers=headers,
    )

    assert response.status_code == 200
    system_prompt = ai_calls[0]
    assert "DOCUMENT EXCERPTS" in system_prompt
    # The most relevant excerpt comes first
    assert system_prompt.index("skills.txt") < system_prompt.index("food.txt")
    # The reply ends with the sources it used
    assert "📄 **Sources:**" in response.json()["reply"]
    assert "skills.txt (p. 1)" in response.json()["reply"]


def test_documents_are_ignored_unless_asked(ai_calls):
    headers = register()
    upload(headers, "skills.txt", "Kruthi writes Python.")

    response = client.post("/api/chat", json=dict(message="Hi"), headers=headers)

    assert "DOCUMENT EXCERPTS" not in ai_calls[0]
    assert "Sources" not in response.json()["reply"]


def test_no_documents_uploaded_tells_the_ai(ai_calls):
    headers = register()

    client.post("/api/chat", json=dict(message="Summarize my notes", use_documents=True),
                headers=headers)

    assert "haven't uploaded any yet" in ai_calls[0]


def test_other_users_documents_are_never_searched(ai_calls):
    kruthi = register("kruthi")
    other = register("someone_else")
    upload(kruthi, "secret.txt", "Kruthi's private Python notes.")

    client.post("/api/chat", json=dict(message="Python?", use_documents=True), headers=other)

    assert "secret.txt" not in ai_calls[0]
    assert "haven't uploaded any yet" in ai_calls[0]


def test_streaming_reply_ends_with_sources(monkeypatch):
    headers = register()
    upload(headers, "skills.txt", "Kruthi writes Python.")
    monkeypatch.setattr(
        chat_routes, "stream_ai_reply",
        lambda messages, system_prompt=None: iter(["She ", "knows Python."]),
    )

    response = client.post(
        "/api/chat/stream",
        json=dict(message="Python skills?", use_documents=True),
        headers=headers,
    )

    assert response.text.startswith("She knows Python.")
    assert response.text.endswith("skills.txt (p. 1)")

    # The saved reply includes the sources too, so they reappear after a refresh
    conversation_id = response.headers["X-Conversation-Id"]
    saved = client.get("/api/conversations/" + conversation_id, headers=headers).json()
    assert saved["messages"][-1]["content"].endswith("skills.txt (p. 1)")