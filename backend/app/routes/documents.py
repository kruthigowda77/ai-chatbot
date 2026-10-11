"""
routes/documents.py - Upload, list, and delete the logged-in user's documents.
"""

from pathlib import PurePath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import config
from app.db.database import get_db
from app.db.models import User
from app.schemas import DocumentOut
from app.services import documents
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a PDF, TXT, or MD file. Its text is split, embedded, and saved."""
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024

    # Read at most one byte more than allowed, so huge files are never fully loaded
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"That file is too large. The limit is {config.MAX_UPLOAD_MB} MB."
        )
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty.")

    # Keep only the name itself: never trust folder paths sent by a browser
    filename = PurePath(file.filename or "document").name[:255] or "document"

    try:
        return documents.add_document(db, user.id, filename, data)
    except documents.DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Your documents, newest first."""
    return documents.list_documents(db, user.id)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Delete one of your documents and all its chunks."""
    document = documents.get_document(db, document_id, user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    documents.delete_document(db, document)