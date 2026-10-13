"""
test_web_search.py - Tests for answering with live web search results.

The search engine and the AI are both faked, so these tests never use the internet.
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.routes import chat as chat_routes
from app.services import web_search

client = TestClient(main.app)

PASSWORD = "password123"

FAKE_RESULTS = [
    web_search.WebResult("India wins the cup", "https://news.example.com/cup", "India won the final."),
    web_search.WebResult("Match report", "https://sport.example.com/report", "A close game."),
]


def register(username="kruthi"):
    response = client.post("/api/auth/register", json=dict(username=username, password=PASSWORD))
    return dict(Authorization="Bearer " + response.json()["access_token"])


@pytest.fixture
def ai_calls(monkeypatch):
    """A fake AI that records the system prompt it receives."""
    calls = []

    def fake_ai(messages, system_prompt=None):
        calls.append(system_prompt)
        return "Fake answer."

    monkeypatch.setattr(chat_routes, "get_ai_reply", fake_ai)
    return calls


@pytest.fixture
def fake_search(monkeypatch):
    """Replace the real search with one that returns FAKE_RESULTS and records queries."""
    queries = []

    def fake(query, max_results=web_search.MAX_RESULTS):
        queries.append(query)
        return FAKE_RESULTS

    monkeypatch.setattr(web_search, "search_web", fake)
    return queries


# ===== Cleaning search results =====

def test_search_keeps_only_normal_links_and_cleans_titles(monkeypatch):
    class FakeDDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, max_results=5):
            return [
                dict(title="Good [page]", href="https://example.com/a b", body="ok"),
                dict(title="Bad", href="javascript:alert(1)", body="evil"),
            ]

    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    results = web_search.search_web("anything")

    assert len(results) == 1
    assert results[0].title == "Good page"
    assert results[0].url == "https://example.com/a%20b"


def test_search_failure_raises_web_search_error(monkeypatch):
    class BrokenDDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, max_results=5):
            raise ConnectionError("no internet")

    monkeypatch.setattr(web_search, "DDGS", BrokenDDGS)

    with pytest.raises(web_search.WebSearchError):
        web_search.search_web("anything")


def test_format_sources_makes_numbered_links():
    note = web_search.format_sources(FAKE_RESULTS)
    assert "🌐 **Web sources:**" in note
    assert "1. [India wins the cup](https://news.example.com/cup)" in note
    assert web_search.format_sources([]) == ""


# ===== Using the web in chat =====

def test_web_results_are_given_to_the_ai(ai_calls, fake_search):
    headers = register()

    response = client.post(
        "/api/chat", json=dict(message="Who won the cup?", use_web=True), headers=headers
    )

    assert response.status_code == 200
    assert fake_search == ["Who won the cup?"]
    assert "WEB SEARCH RESULTS" in ai_calls[0]
    assert "India won the final." in ai_calls[0]
    assert "Today's date is" in ai_calls[0]
    assert "🌐 **Web sources:**" in response.json()["reply"]


def test_web_is_not_searched_unless_asked(ai_calls, fake_search):
    headers = register()

    response = client.post("/api/chat", json=dict(message="Hi"), headers=headers)

    assert fake_search == []
    assert "WEB SEARCH RESULTS" not in ai_calls[0]
    assert "Web sources" not in response.json()["reply"]


def test_search_failure_still_answers(ai_calls, monkeypatch):
    def broken(query, max_results=web_search.MAX_RESULTS):
        raise web_search.WebSearchError("down")

    monkeypatch.setattr(web_search, "search_web", broken)
    headers = register()

    response = client.post(
        "/api/chat", json=dict(message="Latest news?", use_web=True), headers=headers
    )

    assert response.status_code == 200
    assert "web search is unavailable" in ai_calls[0]


def test_streaming_reply_ends_with_web_sources(monkeypatch, fake_search):
    headers = register()
    monkeypatch.setattr(
        chat_routes, "stream_ai_reply",
        lambda messages, system_prompt=None: iter(["India ", "won."]),
    )

    response = client.post(
        "/api/chat/stream", json=dict(message="Who won?", use_web=True), headers=headers
    )

    assert response.text.startswith("India won.")
    assert response.text.endswith("(https://sport.example.com/report)")