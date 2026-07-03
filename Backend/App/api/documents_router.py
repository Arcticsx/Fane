import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

try:
    from ..database import get_db
    from ..models import SourceDocument
    from ..services.process_documents import process_document
except ImportError:
    from database import get_db
    from models import SourceDocument
    from services.process_documents import process_document

router = APIRouter(prefix="/story", tags=["documents"])

UPLOAD_DIR = "app/data/uploads"
ALLOWED_EXTENSIONS = {".pdf"}


@router.post("/{id}/docs")
async def create_story_document(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # 1. Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # 2. Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")

    # 3. Create SourceDocument record (status = "processing")
    source_doc = SourceDocument(
        session_id=id,
        filename=file.filename,
        status="processing",
        chunk_count=0,
    )
    db.add(source_doc)
    db.commit()
    db.refresh(source_doc)

    # 4. Save uploaded file to temp location
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        # If file can't be saved, mark document as failed and re-raise
        source_doc.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")

    # 5. Offload processing to background
    background_tasks.add_task(
        process_document,
        source_doc_id=source_doc.id,
        session_id=id,
        temp_path=temp_path,
        filename=file.filename,
    )

    # 6. Return immediately with processing status
    return {
        "status": "processing",
        "session_id": id,
        "source_document_id": source_doc.id,
        "filename": file.filename,
        "message": "Document is being processed in the background."
    }
    

@router.get("/{id}/docs/{doc_id}/status")
async def get_document_status(
    id: str,
    doc_id: str,
    db: Session = Depends(get_db),
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