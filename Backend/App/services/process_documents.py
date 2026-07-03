import os
import shutil
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SourceDocument
from .documents import chunk_document, embed_chunks
from .vectorstore import save_chunks_to_chromadb


def process_document(
    source_doc_id: str,
    session_id: str,
    temp_path: str,
    filename: str,
):
    """
    Background task: chunk, embed, and store document in Chroma.
    Updates SourceDocument status on completion or failure.
    """
    db = next(get_db())  # create a fresh session for background task

    try:
        # 1. Chunk the document
        chunks = chunk_document(temp_path)
        if not chunks:
            raise ValueError("No content extracted")

        # 2. Generate embeddings
        embeddings = embed_chunks(chunks)

        # 3. Save to Chroma (docs collection)
        result = save_chunks_to_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            session_id=session_id,
            source_pdf=filename,
            collection_type="docs",  # raw PDF chunks
        )

        # 4. Update SourceDocument to "ready"
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            source_doc.status = "ready"
            source_doc.chunk_count = result["chunks_saved"]
            db.commit()

    except Exception as e:
        # 5. On failure, mark document as failed
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            source_doc.status = "failed"
            source_doc.error_message = str(e)[:1000]  # truncate
            db.commit()
        # Optionally log the error

    finally:
        # 6. Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass