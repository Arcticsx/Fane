import os
import shutil
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.rpg_sessions import SourceDocument
from ..models.rpg_sessions import RpgSession  
from .documents import chunk_document, embed_chunks, get_document_metadata, generate_page_windows
from .vectorstore import save_chunks_to_chromadb
from .extraction import extract_beats_from_window, sort_candidates, save_candidate_beats

try:
    from .logging_utils import log_error
except ImportError:
    def log_error(context, error, source_doc_id=None):
        print(f"[{context}] source_doc_id={source_doc_id}: {error}")

# NOTE: the following imports are for functions used ONLY inside the
# commented-out (inactive) blocks below. Left commented so this file does
# not fail to import if these modules don't exist yet.
# from .metadata import get_document_metadata
# from .logging_utils import log_error
# from .map_phase import generate_page_windows, extract_beats_from_window, save_candidate_beats
# from .reduce_phase import reduce_beats_and_chapters, validate_beats_and_chapters, save_final_beats_and_chapters

# ---------------------------------------------------------------------------
# IMPORTANT: everything below marked "# PROPOSED:" is inert -- it is a
# comment, not code, and has ZERO effect on execution as committed. The
# active code path below is IDENTICAL to the original file's behavior.
# ---------------------------------------------------------------------------


def process_document(
    source_doc_id: str,
    session_id: str,
    temp_path: str,
    filename: str,
):
    
    db = next(get_db())  # create a fresh session for background task

    try:
        
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            from datetime import datetime, timezone
            source_doc.processing_started_at = datetime.now(timezone.utc)
            db.commit()

       
        doc_meta = get_document_metadata(temp_path)

        chunks = chunk_document(temp_path)
        if not chunks:
            raise ValueError("No content extracted")

        embeddings = embed_chunks(chunks)

  
        result = save_chunks_to_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            session_id=session_id,
            source_pdf=filename,
            collection_type="docs",  
        )

       
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            source_doc.status = "ready"
            source_doc.chunk_count = result["chunks_saved"]
          
            source_doc.total_pages = doc_meta.get("total_pages")
            source_doc.file_size_bytes = doc_meta.get("file_size_bytes")
            from datetime import datetime, timezone
            source_doc.processing_completed_at = datetime.now(timezone.utc)
            db.commit()

        rpg_session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        if rpg_session:
            rpg_session.setup_status = "extracting"
            db.commit()
            
            total_pages = doc_meta.get("total_pages") or 0
            windows = generate_page_windows(total_pages, window_size=5, overlap=1)
        
            all_candidates = []
            for start_page, end_page in windows:
                try:
                    candidates = extract_beats_from_window(
                        session_id=session_id,
                        source_doc_id=source_doc_id,
                        start_page=start_page,
                        end_page=end_page,
                    )
                    all_candidates.extend(candidates)
                except Exception as window_error:
                    
                    log_error(
                        context=f"map_phase_window[{start_page}-{end_page}]",
                        error=window_error,
                        source_doc_id=source_doc_id,
                    )
                    continue
        
            if all_candidates:
                sorted_candidates = sort_candidates(all_candidates)
                save_candidate_beats(
                    source_doc_id=source_doc_id,
                    session_id=session_id,
                    candidates=sorted_candidates,
                )

    except Exception as e:

        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            source_doc.status = "failed"
            source_doc.error_message = str(e)[:1000]  # truncate
            db.commit()


    finally:
        
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

