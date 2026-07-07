import os
from app.database import get_db
from app.models import SourceDocument
from app.services.documents import chunk_document, embed_chunks
from app.services.vectorstore import save_chunks_to_chromadb


def process_document(
    source_doc_id: str,
    session_id: str,
    temp_path: str,
    filename: str,
):
    with get_db() as db:
        try:
            chunks = chunk_document(temp_path)
            if not chunks:
                raise ValueError("No content extracted")

            # Optimistically record chunk count and mark ready so front-end can proceed.
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.chunk_count = len(chunks)
                source_doc.status = "ready"
                db.commit()

            # Try to embed and persist to vector DB; failures here shouldn't block the
            # user from seeing the uploaded file and its chunks count.
            try:
                embeddings = embed_chunks(chunks)
                result = save_chunks_to_chromadb(
                    chunks=chunks,
                    embeddings=embeddings,
                    session_id=session_id,
                    source_pdf=filename,
                    collection_type="docs",
                )
                # If saving returns a chunks_saved count, update it.
                if source_doc and isinstance(result, dict) and "chunks_saved" in result:
                    source_doc.chunk_count = result["chunks_saved"]
                    db.commit()
            except Exception as e:
                # Log embedding/storage error on the document but keep status 'ready'
                if source_doc:
                    source_doc.error_message = str(e)[:1000]
                    db.commit()

        except Exception as e:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.status = "failed"
                source_doc.error_message = str(e)[:1000]
                db.commit()

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    db.close()
