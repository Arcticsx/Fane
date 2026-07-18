import sys
import json
from datetime import datetime, timezone

from ..utility.getdb import get_db
from ..utility.status import is_step_completed, start_step, complete_step, fail_step
from ...models.rpg_sessions import SourceDocument, ChronicleChapter
from .documents import chunk_document, embed_chunks, get_chapters, get_document_metadata
from .vectorstore import save_chunks_to_chromadb


def run_documents_phase(source_doc_id: str, session_id: str):
    with get_db() as db:
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if not source_doc:
            raise ValueError(f"Source document not found: {source_doc_id}")
        temp_path = source_doc.file_path
        filename = source_doc.filename

    _step_metadata_extraction(source_doc_id, session_id, temp_path)
    _step_chapter_extraction(source_doc_id, session_id, temp_path)
    _step_vector_storage(source_doc_id, session_id, temp_path, filename)


def _step_metadata_extraction(source_doc_id: str, session_id: str, temp_path: str):
    phase = "metadata_extraction"
    with get_db() as db:
        if is_step_completed(db, session_id, phase, phase):
            return

    with get_db() as db:
        try:
            start_step(db, session_id, phase, phase)
        except Exception:
            pass

    try:
        print(f"[run_documents] Extracting metadata from {temp_path}")
        doc_meta = get_document_metadata(temp_path)

        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc and doc_meta:
                source_doc.total_pages = doc_meta["total_pages"]
                source_doc.file_size_bytes = doc_meta["file_size"]
                db.commit()
                print(f"[run_documents] Inserted document metadata: {doc_meta['total_pages']} pages, {doc_meta['file_size']} bytes")

        with get_db() as db:
            complete_step(db, session_id, phase, phase)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, phase, e)
        print(f"[run_documents] Error extracting metadata for {temp_path}: {e}", file=sys.stderr)
        raise


def _step_chapter_extraction(source_doc_id: str, session_id: str, temp_path: str):
    phase = "chapter_extraction"
    with get_db() as db:
        if is_step_completed(db, session_id, phase, phase):
            return

    with get_db() as db:
        try:
            start_step(db, session_id, phase, phase)
        except Exception:
            pass

    try:
        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            total_pages = source_doc.total_pages if source_doc else 0

        chapters = get_chapters(temp_path, total_pages)
        print(f"[run_documents] Extracted {len(chapters)} chapters for {temp_path}")
        print(f"[run_documents] Chapters: {json.dumps(chapters, indent=2)}")

        if chapters:
            with get_db() as db:
                for chapter in chapters:
                    chronicle_chapter = ChronicleChapter(
                        session_id=session_id,
                        number=chapter.get("number"),
                        title=chapter.get("title"),
                        start_page=chapter.get("start_page"),
                        end_page=chapter.get("end_page"),
                        page_range=chapter.get("page_range"),
                        characters=None,
                    )
                    db.add(chronicle_chapter)
                    print(f"[run_documents] Inserted chapter {chapter.get('number')}: '{chapter.get('title')}' pages {chapter.get('start_page')}-{chapter.get('end_page')}")
                try:
                    db.commit()
                    print(f"[run_documents] Inserted {len(chapters)} chapters")
                except Exception as e:
                    print(f"[run_documents] Error committing chapters: {e}", file=sys.stderr)
                    db.rollback()
                    raise

        with get_db() as db:
            complete_step(db, session_id, phase, phase)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, phase, e)
        print(f"[run_documents] Error extracting chapters for {temp_path}: {e}", file=sys.stderr)
        raise

def _step_vector_storage(source_doc_id: str, session_id: str, temp_path: str, filename: str):
    phase = "vector_storage"
    with get_db() as db:
        if is_step_completed(db, session_id, phase, phase):
            return

    with get_db() as db:
        try:
            start_step(db, session_id, phase, phase)
        except Exception:
            pass

    try:
        chunks = chunk_document(temp_path, chunksize=500, overlap=50)
        if not chunks:
            raise ValueError("No content extracted for vector storage")

        embeddings = embed_chunks(chunks)

        print(f"[run_documents] Saving {len(chunks)} chunks to vectorstore")
        result = save_chunks_to_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            session_id=session_id,
            source_pdf=filename,
            collection_type="docs",
        )

        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc and isinstance(result, dict) and "chunks_saved" in result:
                source_doc.chunk_count = result["chunks_saved"]
                source_doc.status = "ready"
                db.commit()

        with get_db() as db:
            complete_step(db, session_id, phase, phase)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, phase, e)
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.error_message = str(e)[:1000]
                db.commit()
        print(f"[run_documents] Error saving chunks to vectorstore for {source_doc_id}: {e}", file=sys.stderr)
        raise
