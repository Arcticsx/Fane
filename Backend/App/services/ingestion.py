import os
import shutil
import uuid
from sqlalchemy.orm import Session

try:
    from .documents import chunk_document, embed_chunks
    from .vectorstore import save_chunks_to_chromadb
    from ..models import SourceDocument
except ImportError:
    from services.documents import chunk_document, embed_chunks
    from services.vectorstore import save_chunks_to_chromadb
    from models import SourceDocument

UPLOAD_DIR = "app/data/uploads"
ALLOWED_EXTENSIONS = {".pdf"}


def ingest_pdf_to_session(
    db: Session, 
    session_id: str, 
    file,           # file-like object from FastAPI UploadFile
    filename: str,
    collection_type: str = "docs"  # "docs" or "lore"
) -> SourceDocument:
    # Validate file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Create upload directory
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")

    # Create SourceDocument row
    source_doc = SourceDocument(
        session_id=session_id,
        filename=filename,
        status="processing",
        chunk_count=0,
    )
    db.add(source_doc)
    db.commit()
    db.refresh(source_doc)

    try:
        # Save uploaded file to temp location
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file, f)

        # Step 1: Chunk the document (returns Documents with page metadata)
        chunks = chunk_document(temp_path)
        if not chunks:
            raise ValueError("No content could be extracted from the document")

        # Step 2: Validate page metadata (critical for page-locked RAG)
        for chunk in chunks:
            page = chunk.metadata.get("page")
            if page is None:
                raise ValueError(
                    f"Chunk missing page metadata. First 100 chars: {chunk.page_content[:100]}..."
                )
            if not isinstance(page, int) or page < 1:
                raise ValueError(f"Invalid page number: {page}")

        # Step 3: Generate embeddings
        embeddings = embed_chunks(chunks)
        if len(embeddings) != len(chunks):
            raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")

        # Step 4: Save to Chroma
        result = save_chunks_to_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            session_id=session_id,
            source_pdf=filename,
            collection_type=collection_type,  # ✅ FIXED: "docs" for raw PDF
        )

        # Step 5: Update SourceDocument
        source_doc.status = "ready"
        source_doc.chunk_count = result["chunks_saved"]
        db.commit()
        
        return source_doc

    except Exception as e:
        # Log the error (use your logger)
        print(f"PDF ingestion failed: {str(e)}")
        source_doc.status = "failed"
        db.commit()
        raise  # Re-raise so the caller can handle the HTTP error

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass  # Log but don't fail


# ⚡ OPTIONAL: Background Task Version (for FastAPI)
def ingest_pdf_background(
    db: Session,
    session_id: str,
    file,           # UploadFile
    filename: str,
):
    """
    Run ingestion in background to avoid HTTP timeout.
    
    Usage in FastAPI:
        background_tasks.add_task(ingest_pdf_background, next(db), session_id, file, filename)
        return {"message": "Processing started", "source_document_id": source_doc.id}
    """
    try:
        # Re-open the file (FastAPI uploads can only be read once)
        file.file.seek(0)  # Rewind if needed
        ingest_pdf_to_session(db, session_id, file.file, filename)
    except Exception as e:
        print(f"Background ingestion failed: {str(e)}")
        # Optionally notify the user via websocket/email