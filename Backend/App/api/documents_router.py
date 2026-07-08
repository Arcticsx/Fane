import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db_session
from ..models import SourceDocument
from ..models.rpg_sessions import RpgSession
from ..services.process_documents import process_story_beats

router = APIRouter(prefix="/story", tags=["documents"])

UPLOAD_DIR = Path(DATA_DIR) / "files"
ALLOWED_EXTENSIONS = {".pdf"}


@router.post("/{id}/docs")
async def create_story_document(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),        # ← changed
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{id[:8]}_{uuid.uuid4().hex}_{Path(file.filename or 'upload.pdf').name}"
    file_path = UPLOAD_DIR / safe_name

    source_doc = SourceDocument(
        session_id=id,
        filename=file.filename,
        status="processing",
        chunk_count=0,
        file_path=str(file_path),
    )
    db.add(source_doc)
    db.commit()
    db.refresh(source_doc)

    session = db.query(RpgSession).filter(RpgSession.id == id).first()
    if session:
        session.setup_status = "processing"
        session.setup_error = None
        db.commit()

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        source_doc.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")

    background_tasks.add_task(
        process_story_beats,
        source_doc_id=source_doc.id,
        session_id=id,
        temp_path=str(file_path),
        filename=file.filename,
    )

    return {
        "status": "processing",
        "session_id": id,
        "source_document_id": source_doc.id,
        "filename": file.filename,
        "file_path": str(file_path),
        "file_url": f"/data/files/{file_path.name}",
        "message": "Document is being processed in the background."
    }


@router.get("/{id}/docs/{doc_id}/status")
async def get_document_status(
    id: str,
    doc_id: str,
    db: Session = Depends(get_db_session),        # ← changed
):
    doc = db.query(SourceDocument).filter(
        SourceDocument.session_id == id,
        SourceDocument.id == doc_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "source_document_id": doc.id,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
    }