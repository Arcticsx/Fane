import os

from ..database import get_db
from ..models.rpg_sessions import RpgSession, SourceDocument
from .documents import generate_page_windows
from .extraction import extract_beats_from_window, replace_candidates_with_final_beats
from .beats_reduce import run_reduce_phase
from .beats_graph import run_graph_phase
from .graph import persist_beat_graph


def process_story_beats(
    session_id: str,
    source_document_id: str,
):

    db = next(get_db())  # create a fresh session for background task

    try:

        session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        if session:
            session.setup_status = "extracting"
            db.commit()

        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
        if not source_doc or not source_doc.total_pages:
            raise ValueError("Source document missing or has no total_pages")

        windows = generate_page_windows(total_pages=source_doc.total_pages, window_size=10, overlap=2)

        candidate_beats = []
        for window in windows:
            candidate_beats.extend(
                extract_beats_from_window(
                    window=window,
                    session_id=session_id,
                    source_document_id=source_document_id,
                )
            )

        if not candidate_beats:
            raise ValueError("No beats extracted")

        final_beats = run_reduce_phase(db, session_id, candidate_beats)

        graph_edges = run_graph_phase(db, session_id, final_beats)

        if session:
            session.setup_status = "ready"
            db.commit()

    except Exception as e:
        session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
        if session:
            session.setup_status = "failed"
            session.setup_error = str(e)[:1000]
            db.commit()

    finally:
        pass
