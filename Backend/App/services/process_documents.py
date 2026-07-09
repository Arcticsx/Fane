import os
import sys
from datetime import datetime, timezone
from ..database import get_db
from ..models import SourceDocument
from .documents import chunk_document, embed_chunks, get_document_metadata
from .vectorstore import save_chunks_to_chromadb
from .extraction import extract_beats_from_window, replace_candidates_with_final_beats
from .beats_reduce import run_reduce_phase
from .beats_graph import run_graph_phase
from .process_story_beats import process_story_beats


def process_document(
    source_doc_id: str,
    session_id: str,
    temp_path: str,
    filename: str,
):
    try:
        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.processing_started_at = datetime.now(timezone.utc)
                db.commit()

            try:
                doc_meta = get_document_metadata(temp_path)
            except Exception as e:
                print(f"[process_document] Error getting metadata for {temp_path}: {e}", file=sys.stderr)
                raise

            try:
                chunks = chunk_document(temp_path, chunksize=500, overlap=50)
            except Exception as e:
                print(f"[process_document] Error chunking document {temp_path}: {e}", file=sys.stderr)
                raise
            if not chunks:
                raise ValueError("No content extracted")

            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.chunk_count = len(chunks)
                source_doc.status = "ready"
                db.commit()

            try:
                embeddings = embed_chunks(chunks)
            except Exception as e:
                print(f"[process_document] Error creating embeddings for {source_doc_id}: {e}", file=sys.stderr)
                if source_doc:
                    source_doc.error_message = str(e)[:1000]
                    db.commit()
                raise

            try:
                result = save_chunks_to_chromadb(
                    chunks=chunks,
                    embeddings=embeddings,
                    session_id=session_id,
                    source_pdf=filename,
                    collection_type="docs",
                )
                if source_doc and isinstance(result, dict) and "chunks_saved" in result:
                    source_doc.chunk_count = result["chunks_saved"]
                    db.commit()
            except Exception as e:
                print(f"[process_document] Error saving chunks to vectorstore for {source_doc_id}: {e}", file=sys.stderr)
                if source_doc:
                    source_doc.error_message = str(e)[:1000]
                    db.commit()
                raise

            try:
                process_story_beats(session_id=session_id, source_document_id=source_doc_id)
            except Exception as e:
                print(f"[process_document] Error processing story beats for {source_doc_id}: {e}", file=sys.stderr)
                with get_db() as db:
                    sd = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
                    if sd:
                        sd.error_message = str(e)[:1000]
                        sd.status = "failed"
                        db.commit()
                raise

    except Exception as e:
        # Open a fresh session — the one above may already be rolled back/closed
        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.status = "failed"
                source_doc.error_message = str(e)[:1000]
                db.commit()

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e:
                print(f"[process_document] Failed to remove temp file {temp_path}: {e}", file=sys.stderr)