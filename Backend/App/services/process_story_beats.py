import os
import sys

from ..database import get_db
from ..models.rpg_sessions import RpgSession, SourceDocument
from .documents import generate_page_windows
from .extraction import extract_beats_from_window, replace_candidates_with_final_beats, save_candidate_beats
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

                import time

                windows = generate_page_windows(total_pages=source_doc.total_pages, window_size=5, overlap=1)
                candidate_beats = []
                consecutive_failures = 0

                for start_page, end_page in windows:
                    try:
                        beats = extract_beats_from_window(session_id, source_document_id, start_page, end_page)
                        candidate_beats.extend(beats)
                        consecutive_failures = 0
                    except Exception as e:
                        consecutive_failures += 1
                        print(
                            f"[process_story_beats] Error extracting pages {start_page}-{end_page} "
                            f"for {source_document_id}: {e}",
                            file=sys.stderr,
                        )
                        # If the local model server itself is down, back off harder before
                        # hammering it with the next window's request.
                        if "connection refused" in str(e).lower() or "server disconnected" in str(e).lower():
                            print(f"[process_story_beats] Ollama appears unresponsive, backing off 15s", file=sys.stderr)
                            time.sleep(15)
                            beats = extract_beats_from_window(session_id, source_document_id, start_page, end_page)
                        if consecutive_failures >= 5:
                            raise RuntimeError(
                                f"Too many consecutive extraction failures ({consecutive_failures}); "
                                f"aborting rather than continuing to degrade"
                            )
                    finally:
                        time.sleep(1.5)  # cooldown between every window, success or failure

                if not candidate_beats:
                    raise ValueError("No beats extracted")
                else:
                    save_candidate_beats(candidates=candidate_beats, session_id=session_id, source_doc_id=source_document_id)

                final_beats = run_reduce_phase(db, session_id, candidate_beats, source_document_id)

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