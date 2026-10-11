"""
test_documents.py - Tests for uploading, chunking, listing, and deleting documents.

Embeddings are faked, so these tests never call the real AI.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config, main
from app.db.database import SessionLocal
from app.db.models import DocumentChunk
from app.services import documents

client = TestClient(main.app)

PASSWORD = "password123"


def register(username="kruthi"):
    response = client.post("/api/auth/register", json=dict(username=username, password=PASSWORD))
    assert response.status_code == 201, response.text
    return dict(Authorization="Bearer " + response.json()["access_token"])


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    """Every text becomes a tiny 3-number 'embedding' instead of calling the AI."""
    def fake_embed(texts):
        return [[float(len(t)), 1.0, 0.5] for t in texts]

    monkeypatch.setattr(documents, "embed_texts", fake_embed)


def upload(headers, filename="notes.txt", content=b"Python is a programming language. " * 5,
           content_type="text/plain"):
    return client.post(
        "/api/documents",
        files=dict(file=(filename, content, content_type)),
        headers=headers,
    )


# ===== Chunking (no API involved) =====

def test_short_text_is_one_chunk():
    chunks = documents.chunk_text([(1, "Hello   world.\n\nSecond line.")])
    assert chunks == [(1, "Hello world. Second line.")]


def test_long_text_is_split_with_overlap():
    words = " ".join("word" + str(i) for i in range(1000))  # about 7,000 characters
    chunks = documents.chunk_text([(3, words)], size=1000, overlap=200)

    assert len(chunks) > 5
    assert all(page == 3 for page, _ in chunks)
    assert all(len(text) <= 1000 for _, text in chunks)

    # Neighbouring chunks share some text (the overlap)
    first, second = chunks[0][1], chunks[1][1]
    assert first[-50:] in second

    # No word is cut in half at the start of a chunk
    assert all(text.split(" ")[0].startswith("word") for _, text in chunks)


# ===== Uploading =====

def test_upload_text_file_saves_chunks():
    headers = register()

    response = upload(headers)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["filename"] == "notes.txt"
    assert data["num_pages"] == 1
    assert data["num_chunks"] == 1
    assert "embedding" not in data  # embeddings never leave the server

    with SessionLocal() as db:
        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.document_id == data["id"]))
    assert chunk.page == 1
    assert "Python" in chunk.text
    assert len(json.loads(chunk.embedding)) == 3


def test_uploaded_document_is_listed():
    headers = register()
    upload(headers, filename="resume.md", content_type="text/markdown")

    listed = client.get("/api/documents", headers=headers).json()

    assert [d["filename"] for d in listed] == ["resume.md"]


def test_unsupported_file_type_is_rejected():
    headers = register()
    response = upload(headers, filename="virus.exe", content_type="application/octet-stream")
    assert response.status_code == 400


def test_empty_file_is_rejected():
    headers = register()
    response = upload(headers, content=b"")
    assert response.status_code == 400


def test_whitespace_only_file_is_rejected():
    headers = register()
    response = upload(headers, content=b"   \n\n   ")
    assert response.status_code == 400


def test_too_large_file_is_rejected(monkeypatch):
    headers = register()
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)  # any non-empty file is now "too large"

    response = upload(headers)

    assert response.status_code == 413


def test_folder_paths_are_removed_from_filenames():
    headers = register()
    response = upload(headers, filename="../../secret/notes.txt")
    assert response.json()["filename"] == "notes.txt"


# ===== Privacy and deleting =====

def test_documents_require_login():
    assert client.get("/api/documents").status_code == 401


def test_users_cannot_see_or_delete_each_others_documents():
    kruthi = register("kruthi")
    other = register("someone_else")
    document_id = upload(kruthi).json()["id"]

    assert client.get("/api/documents", headers=other).json() == []
    assert client.delete("/api/documents/" + document_id, headers=other).status_code == 404
    assert len(client.get("/api/documents", headers=kruthi).json()) == 1


def test_delete_document_removes_its_chunks():
    headers = register()
    document_id = upload(headers).json()["id"]

    assert client.delete("/api/documents/" + document_id, headers=headers).status_code == 204

    assert client.get("/api/documents", headers=headers).json() == []
    with SessionLocal() as db:
        remaining = db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).all()
    assert remaining == []