import os
import sys

from ..database import get_db
from ..models.rpg_sessions import RpgSession, SourceDocument
from .documents import generate_page_windows
from .extraction import extract_beats_from_window, replace_candidates_with_final_beats
from .beats_reduce import run_reduce_phase
from .beats_graph import run_graph_phase


def process_story_beats(
    session_id: str,
    source_document_id: str,
):
    

    try:
        with get_db() as db:
            session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
            if session:
                session.setup_status = "extracting"
                db.commit()

                source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
                if not source_doc or not source_doc.total_pages:
                    raise ValueError("Source document missing or has no total_pages")

                windows = generate_page_windows(total_pages=source_doc.total_pages, window_size=10, overlap=2)

                candidate_beats = []
                # windows are tuples (start_page, end_page)
                for start_page, end_page in windows:
                    try:
                        beats = extract_beats_from_window(session_id, source_document_id, start_page, end_page)
                        candidate_beats.extend(beats)
                    except Exception as e:
                        print(f"[process_story_beats] Error extracting pages {start_page}-{end_page} for {source_document_id}: {e}", file=sys.stderr)
                        # continue processing remaining windows

                if not candidate_beats:
                    raise ValueError("No beats extracted")

                final_beats = run_reduce_phase(db, session_id, candidate_beats)

                graph_edges = run_graph_phase(db, session_id, final_beats)

                if session:
                    session.setup_status = "ready"
                    db.commit()

    except Exception as e:
        print(f"[process_story_beats] Fatal error for session {session_id}, source {source_document_id}: {e}", file=sys.stderr)
        with get_db() as db:
            session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
            if session:
                session.setup_status = "failed"
                session.setup_error = str(e)[:1000]
                db.commit()

    finally:
        
        pass