"""
documents.py - Turning uploaded files into searchable chunks.

The pipeline for one upload:
    file bytes -> pages of text -> overlapping chunks -> embeddings -> database
"""

import io
import json
import logging
import re

import openai
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db.models import Document, DocumentChunk
from app.services.llm import _translate_error, client

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")
CHUNK_SIZE = 1000      # characters per chunk (roughly a long paragraph)
CHUNK_OVERLAP = 200    # characters shared between neighbouring chunks
MAX_CHUNKS = 500       # protects your API quota from huge documents
EMBED_BATCH_SIZE = 50  # how many chunks to embed in one API request


class DocumentError(Exception):
    """A problem with the uploaded file itself. The message is safe to show users."""


# ===== 1. Extract text =====

def extract_pages(filename: str, data: bytes) -> list[tuple[int, str]]:
    """Return the text of each page as (page_number, text), page numbers starting at 1."""
    name = filename.lower()

    if name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except (PdfReadError, ValueError, KeyError) as e:
            logger.warning("Could not read PDF %s: %s", filename, e)
            raise DocumentError("That PDF couldn't be read. It may be damaged or password-protected.")
    elif name.endswith((".txt", ".md")):
        pages = [(1, data.decode("utf-8", errors="replace"))]
    else:
        raise DocumentError("Only PDF, TXT, and MD files are supported.")

    if not any(text.strip() for _, text in pages):
        raise DocumentError(
            "No text was found in that file. Scanned PDFs (pictures of pages) aren't supported yet."
        )
    return pages


# ===== 2. Split into chunks =====

def chunk_text(
    pages: list[tuple[int, str]], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[tuple[int, str]]:
    """
    Split each page into overlapping chunks of about `size` characters.
    Returns (page_number, chunk_text) pairs.

    The overlap means a sentence cut at the end of one chunk also appears
    at the start of the next, so no idea is lost at a boundary.
    """
    chunks = []
    for page_number, raw_text in pages:
        text = re.sub(r"\s+", " ", raw_text).strip()  # tidy spaces and line breaks
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # Prefer to end at a space, so words aren't cut in half
                space = text.rfind(" ", start + size // 2, end)
                if space > start:
                    end = space
            piece = text[start:end].strip()
            if piece:
                chunks.append((page_number, piece))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks


# ===== 3. Embed =====

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn texts into embeddings, a batch at a time. Raises LLMServiceError on API problems."""
    vectors = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        try:
            response = client.embeddings.create(model=config.EMBEDDING_MODEL, input=batch)
        except openai.APIError as e:
            raise _translate_error(e) from e
        vectors.extend(item.embedding for item in response.data)
    return vectors


# ===== 4. Save =====

def add_document(db: Session, user_id: int, filename: str, data: bytes) -> Document:
    """Run the whole pipeline for one uploaded file and save the result."""
    pages = extract_pages(filename, data)
    chunks = chunk_text(pages)

    if len(chunks) > MAX_CHUNKS:
        raise DocumentError(
            f"That document is too long ({len(chunks)} sections; the limit is {MAX_CHUNKS})."
        )

    vectors = embed_texts([text for _, text in chunks])

    document = Document(
        user_id=user_id,
        filename=filename,
        num_pages=len(pages),
        num_chunks=len(chunks),
    )
    for index, ((page, text), vector) in enumerate(zip(chunks, vectors)):
        document.chunks.append(DocumentChunk(
            chunk_index=index,
            page=page,
            text=text,
            # Rounding keeps the stored JSON smaller without changing search results
            embedding=json.dumps([round(x, 6) for x in vector]),
        ))

    db.add(document)
    db.commit()  # the document and all its chunks are saved together, or not at all
    logger.info("Saved document %s (%d pages, %d chunks)", filename, len(pages), len(chunks))
    return document


def list_documents(db: Session, user_id: int) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(statement))


def get_document(db: Session, document_id: str, user_id: int) -> Document | None:
    """The document, only if it belongs to this user."""
    statement = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    return db.scalar(statement)


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)  # its chunks are deleted too (cascade)
    db.commit()