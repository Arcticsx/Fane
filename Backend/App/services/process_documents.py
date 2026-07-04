import os
import shutil
from sqlalchemy.orm import Session
from database import get_db
from models import SourceDocument
# from models import RpgSession  # only needed by the inactive CHANGE 4 block below
from .documents import chunk_document, embed_chunks
from .vectorstore import save_chunks_to_chromadb

# NOTE: the following imports are for functions used ONLY inside the
# commented-out (inactive) blocks below. Left commented so this file does
# not fail to import if these modules don't exist yet.
# from .metadata import get_document_metadata
# from .logging_utils import log_error
# from .map_phase import generate_page_windows, extract_beats_from_window, save_candidate_beats

# ---------------------------------------------------------------------------
# FULL LOG: ALL ARBITRARY ABSTRACTED FUNCTIONS REFERENCED IN THIS FILE
# ("abstracted" = implementation lives elsewhere; this file only calls them)
# ---------------------------------------------------------------------------
# | # | Function                                                                          | Status              | Source module    | Called at (if active)              | Params (in)                                                          | Returns (out)                                                | Purpose                                                                |
# |---|-------------------------------------------------------------------------------------|---------------------|-------------------|-------------------------------------|-----------------------------------------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------|
# | 1 | get_db()                                                                             | ACTIVE (unchanged)  | database          | Top of process_document             | none                                                                    | generator yielding a Session                                    | Provides a DB session for the background task                            |
# | 2 | chunk_document(temp_path)                                                            | ACTIVE (unchanged)  | .documents        | Step 1                              | temp_path: str                                                          | chunks: list (must carry page_number metadata per chunk)        | Splits PDF into semantic chunks                                          |
# | 3 | embed_chunks(chunks)                                                                 | ACTIVE (unchanged)  | .documents        | Step 2                              | chunks: list                                                            | embeddings: list                                                | Generates vector embeddings per chunk                                    |
# | 4 | save_chunks_to_chromadb(chunks, embeddings, session_id, source_pdf, collection_type) | ACTIVE (unchanged)  | .vectorstore      | Step 3                              | as named                                                                | result: dict with "chunks_saved": int                          | Persists chunks+embeddings to session-scoped Chroma collection           |
# | 5 | get_document_metadata(temp_path)                                                     | COMMENTED OUT       | .metadata         | Start of try, before chunking       | temp_path: str                                                          | dict: {"total_pages": int, "file_size_bytes": int}              | Populates SourceDocument.total_pages / file_size_bytes                   |
# | 6 | log_error(context, error, source_doc_id)                                             | COMMENTED OUT       | .logging_utils    | except block AND per-window catch   | context: str, error: Exception, source_doc_id: str                     | None                                                            | Centralized error logging (would replace old bare comment)               |
# | 7 | generate_page_windows(total_pages, window_size=5, overlap=1)                         | COMMENTED OUT       | .map_phase        | Start of MAP loop                   | total_pages: int, window_size: int, overlap: int                       | list[tuple[int, int]] of (start_page, end_page)                 | Builds MAP-phase window schedule (step = window_size - overlap)         |
# | 8 | extract_beats_from_window(session_id, source_doc_id, start_page, end_page)           | COMMENTED OUT       | .map_phase        | Inside per-window MAP loop          | session_id: str, source_doc_id: str, start_page: int, end_page: int    | list[dict] candidate beats (order, description, start/end page) | MAP step: LLM call scoped to one window's Chroma chunks                 |
# | 9 | save_candidate_beats(source_doc_id, session_id, candidates)                          | COMMENTED OUT       | .map_phase        | After MAP loop, if candidates found | source_doc_id: str, session_id: str, candidates: list[dict]            | int (count saved)                                               | Stages raw MAP candidates ahead of the (separate) Reduce step            |
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
    """
    Background task: chunk, embed, and store document in Chroma.
    Updates SourceDocument status on completion or failure.
    """
    db = next(get_db())  # create a fresh session for background task

    try:
        # --- CHANGE 1 (PROPOSED, inactive): set processing_started_at --------
        # PROPOSED:
        #     source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        #     if source_doc:
        #         from datetime import datetime, timezone
        #         source_doc.processing_started_at = datetime.now(timezone.utc)
        #         db.commit()

        # --- CHANGE 2 (PROPOSED, inactive): capture doc metadata --------------
        # PROPOSED:
        #     doc_meta = get_document_metadata(temp_path)

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
            # --- CHANGE 3 (PROPOSED, inactive): extra fields on this block ----
            # PROPOSED (would be added here, before the db.commit() below):
            #     source_doc.total_pages = doc_meta.get("total_pages")
            #     source_doc.file_size_bytes = doc_meta.get("file_size_bytes")
            #     from datetime import datetime, timezone
            #     source_doc.processing_completed_at = datetime.now(timezone.utc)
            db.commit()

        # --- CHANGE 4 (PROPOSED, inactive): Phase 0 -> Phase 1 handoff --------
        # PROPOSED:
        #     rpg_session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        #     if rpg_session:
        #         rpg_session.setup_status = "extracting"
        #         db.commit()

        # --- CHANGE 5 & 6 (PROPOSED, inactive): Phase 1 MAP phase --------------
        # Consolidate into calling MAP with 5-page windows, 1-page overlap
        # (step = window_size - overlap = 4 pages), per current instructions
        # (spec originally called for 10-page/8-step/2-overlap).
        # PROPOSED:
        #     total_pages = doc_meta.get("total_pages") or 0
        #     windows = generate_page_windows(total_pages, window_size=5, overlap=1)
        #
        #     all_candidates = []
        #     for start_page, end_page in windows:
        #         try:
        #             candidates = extract_beats_from_window(
        #                 session_id=session_id,
        #                 source_doc_id=source_doc_id,
        #                 start_page=start_page,
        #                 end_page=end_page,
        #             )
        #             all_candidates.extend(candidates)
        #         except Exception as window_error:
        #             # per-window failure: logged and skipped, not fatal --
        #             # one bad window should not undo a successful chunk/embed/store.
        #             log_error(
        #                 context=f"map_phase_window[{start_page}-{end_page}]",
        #                 error=window_error,
        #                 source_doc_id=source_doc_id,
        #             )
        #             continue
        #
        #     if all_candidates:
        #         save_candidate_beats(
        #             source_doc_id=source_doc_id,
        #             session_id=session_id,
        #             candidates=all_candidates,
        #         )

    except Exception as e:
        # --- CHANGE 7 (PROPOSED, inactive): rollback before re-querying -------
        # PROPOSED (would be inserted as the first line of this except block):
        #     db.rollback()

        # 5. On failure, mark document as failed
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if source_doc:
            source_doc.status = "failed"
            source_doc.error_message = str(e)[:1000]  # truncate
            db.commit()
        # Optionally log the error
        # --- CHANGE 8 (PROPOSED, inactive): real error logging ----------------
        # PROPOSED (would replace the "Optionally log the error" comment above):
        #     log_error(context="process_document", error=e, source_doc_id=source_doc_id)

    finally:
        # 6. Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        # --- CHANGE 9 (PROPOSED, inactive): close the DB session --------------
        # PROPOSED (would be inserted as the last line of this finally block):
        #     db.close()
