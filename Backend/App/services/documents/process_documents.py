import os
import sys
import threading
from datetime import datetime, timezone

from ..utility.getdb import get_db
from ..utility.status import init_pipeline_phases
from ...models.rpg_sessions import SourceDocument
from .run_documents_phase import run_documents_phase
from ..beats.run_beats_phase import run_beats_phase
from ..entities.run_entities_phase import run_entities_phase


def _heartbeat_loop(session_id, stop_event, interval_seconds=5):
    while not stop_event.wait(interval_seconds):
        try:
            with get_db() as db:
                source_doc = (
                    db.query(SourceDocument)
                    .filter(SourceDocument.session_id == session_id)
                    .first()
                )
                if source_doc:
                    source_doc.last_heartbeat = datetime.now(timezone.utc)
                    db.commit()
        except Exception as e:
            print(f"[heartbeat] Failed to update heartbeat for session {session_id}: {e}", file=sys.stderr)


def process_document(
    source_doc_id: str,
    session_id: str,
    temp_path: str,
    filename: str,
):
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(session_id, stop_heartbeat),
        daemon=True,
    )

    try:
        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.processing_started_at = datetime.now(timezone.utc)
                source_doc.last_heartbeat = datetime.now(timezone.utc)
                source_doc.status = "processing"
                db.commit()

        init_pipeline_phases(db, session_id)

        heartbeat_thread.start()

        run_documents_phase(source_doc_id, session_id)
        run_beats_phase(source_doc_id, session_id)
        run_entities_phase(source_doc_id, session_id)

        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.status = "completed"
                source_doc.processing_completed_at = datetime.now(timezone.utc)
                db.commit()

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e:
                print(f"[process_document] Failed to remove temp file {temp_path}: {e}", file=sys.stderr)

    except Exception as e:
        with get_db() as db:
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if source_doc:
                source_doc.status = "failed"
                source_doc.error_message = str(e)[:1000]
                db.commit()
        raise
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)