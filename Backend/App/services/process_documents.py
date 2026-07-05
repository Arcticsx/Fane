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

        # =====================================================================
        # PROPOSED, INACTIVE -- Phase 1a: MAP
        # =====================================================================
        # Split the novel into 5-page windows with 1-page overlap
        # (step = window_size - overlap = 4 pages), per current instructions.
        # (Spec originally called for 10-page/8-step/2-overlap windows.)
        # For each window, fetch Chroma chunks in page order and prompt the
        # LLM to extract mandatory plot beats. A single bad window is logged
        # and skipped rather than failing the whole document.
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
        # =====================================================================
        # END Phase 1a: MAP
        # =====================================================================

        # =====================================================================
        # PROPOSED, INACTIVE -- Phase 1b: REDUCE
        # =====================================================================
        # Spec 1.2: merge all MAP candidates into a final list of 20-50 master
        # beats via a second LLM call; also extract novel chapter boundaries.
        # Spec 1.3: strict Pydantic validation (sequential order, non-overlapping
        # pages, start_page <= end_page for beats; sequential/non-overlapping/
        # full-coverage for chapters). Retry Reduce up to 3x on failure, else
        # fail setup_status.
        # PROPOSED:
        #     MAX_REDUCE_ATTEMPTS = 3
        #     reduce_result = None
        #     validation_errors = []
        #
        #     for attempt in range(1, MAX_REDUCE_ATTEMPTS + 1):
        #         try:
        #             candidate_result = reduce_beats_and_chapters(
        #                 source_doc_id=source_doc_id,
        #                 session_id=session_id,
        #                 candidates=all_candidates,
        #             )
        #         except Exception as reduce_error:
        #             log_error(
        #                 context=f"reduce_phase_attempt[{attempt}]",
        #                 error=reduce_error,
        #                 source_doc_id=source_doc_id,
        #             )
        #             continue
        #
        #         is_valid, validation_errors = validate_beats_and_chapters(
        #             beats=candidate_result.get("beats", []),
        #             chapters=candidate_result.get("chapters", []),
        #             total_pages=total_pages,
        #         )
        #         if is_valid:
        #             reduce_result = candidate_result
        #             break
        #         else:
        #             log_error(
        #                 context=f"reduce_validation_attempt[{attempt}]",
        #                 error=ValueError("; ".join(validation_errors)),
        #                 source_doc_id=source_doc_id,
        #             )
        #
        #     if reduce_result is None:
        #         # All 3 Reduce attempts failed validation -- fail setup_status
        #         # per spec 1.3 ("else fail setup_status").
        #         rpg_session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        #         if rpg_session:
        #             rpg_session.setup_status = "failed"
        #             db.commit()
        #     else:
        #         # Persist final beats + chapters (spec 1.2 output), e.g. into
        #         # StoryBeat and chronicle_chapters / NovelChapter tables.
        #         save_final_beats_and_chapters(
        #             source_doc_id=source_doc_id,
        #             session_id=session_id,
        #             beats=reduce_result["beats"],
        #             chapters=reduce_result["chapters"],
        #         )
        #         # Advance setup_status past Reduce -- spec 1.4 picks up next
        #         # with character/lore summary population.
        #         rpg_session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        #         if rpg_session:
        #             rpg_session.setup_status = "reduced"
        #             db.commit()
        # =====================================================================
        # END Phase 1b: REDUCE
        # =====================================================================


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
