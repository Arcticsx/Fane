import os
import sys
from datetime import datetime, timezone
import json
from ..database import get_db
from ..models.rpg_sessions import SourceDocument, ChronicleChapter
from .documents import chunk_document, embed_chunks, get_chapters, get_document_metadata
from .vectorstore import save_chunks_to_chromadb
from .process_story_beats import process_story_beats
from .process_entities import process_entities
from .process_characters import process_characters
from ...tests.test_characters import characters



# THIS IS A TEST DATASET FOR CHARACTERS



from ..models.document_status import update_phase_status

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
                print(f"[process_document] Path = {temp_path}")
                doc_meta = get_document_metadata(temp_path)
            except Exception as e:
                print(f"[process_document] Error getting metadata for {temp_path}: {e}", file=sys.stderr)
                raise
            
            if doc_meta:
                source_doc.total_pages = doc_meta["total_pages"]
                source_doc.file_size_bytes = doc_meta["file_size"]
                print(f"Inserted document metadata")
            else:
                print(f"No document metadata")

            try:
                chapters = get_chapters(temp_path, doc_meta["total_pages"])
                print(f"[process_document] Extracted {len(chapters)} chapters for {temp_path}")
                print(f"[process_document] Chapters: {json.dumps(chapters, indent=2)}")
            except Exception as e:
                print(f"[process_document] Error extracting chapters for {temp_path}: {e}", file=sys.stderr)
                raise
            
            if chapters:
                print(f"[process_document] Inserting {len(chapters)} chapters into database for session {session_id}")
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
                    print(f"Inserted chapter {chapter.get('number')}: '{chapter.get('title')}' pages {chapter.get('start_page')}-{chapter.get('end_page')}")
                try:
                    db.commit()
                    print(f"Inserted {len(chapters)} chapters")
                except Exception as e:
                    print(f"[process_document] Error committing chapters to database for session {session_id}: {e}", file=sys.stderr)
                    db.rollback()
                    raise
            else:
                print(f"No chapters extracted")
                        
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
            
            try:
                characters,lore = process_entities(session_id=session_id, source_document_id=source_doc_id)
            except Exception as e:
                print(f"[process_document] Error processing entities for {source_doc_id}: {e}", file=sys.stderr)
                with get_db() as db:
                    sd = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
                    if sd:
                        sd.error_message = str(e)[:1000]
                        sd.status = "failed"
                        db.commit()
                raise
            
           
            try:
                process_characters(session_id=session_id, source_document_id=source_doc_id, characters=characters)
            except Exception as e:
                print(f"[process_document] Error processing characters for {source_doc_id}: {e}", file=sys.stderr)
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