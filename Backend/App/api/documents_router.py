from datetime import datetime, timezone
from pathlib import Path

from Backend.App.models.rpg_sessions import ProcessStatus
from ..services.documents.documents import create_source_document
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, logger
from sqlalchemy.orm import Session
from ..services.utility.getdb import get_db_session
from ..services.utility.config import DATA_DIR
from ..models import SourceDocument
from ..services.documents.process_documents import process_document


router = APIRouter(prefix="/story", tags=["documents"])


@router.post("/{id}/docs")
async def create_story_document(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    try:
        source_doc = create_source_document(db, id, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to save uploaded document")
        raise HTTPException(status_code=500, detail="Could not save uploaded file")

    background_tasks.add_task(
        process_document,
        source_doc_id=source_doc.id,
        session_id=id,
        temp_path=source_doc.file_path,
        filename=file.filename,
    )

    return {
        "status": "processing",
        "session_id": id,
        "source_document_id": source_doc.id,
        "filename": file.filename,
        "file_path": source_doc.file_path,
        "file_url": f"/data/files/{Path(source_doc.file_path).name}",
        "message": "Document is being processed in the background.",
    }


@router.get("/{id}/docs/{doc_id}/status")
async def get_document_status(
    id: str,
    doc_id: str,
    db: Session = Depends(get_db_session),
):
    doc = db.query(SourceDocument).filter(
        SourceDocument.session_id == id,
        SourceDocument.id == doc_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "processing":
        heartbeat_deadline = (
            doc.last_heartbeat.timestamp() + 300
            if doc.last_heartbeat else 0
        )
        if datetime.now(timezone.utc).timestamp() > heartbeat_deadline:
            doc.status = "failed"
            doc.error_message = "Server crashed"
            doc.processing_completed_at = datetime.now(timezone.utc)
            process_status = db.query(ProcessStatus).filter(ProcessStatus.session_id == id).all()
            for status in process_status:
                if status.status == "processing":
                    status.status = "failed"
            db.commit()

    return {
        "source_document_id": doc.id,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
    }



