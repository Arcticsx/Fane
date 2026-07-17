from .getdb import get_db
from ...models.rpg_sessions import ProcessStatus
import sys
import logging

logger = logging.getLogger(__name__)


PIPELINE_PHASES = {
    "document_upload": "pending",
    "chunking": "pending",
    "embedding": "pending",
}

def initialize_status(db, session_id):
    
    existing_phases = {
        row.phase for row in
        db.query(ProcessStatus.phase).filter_by(session_id=session_id).all()
    }
    for phase, status in PIPELINE_PHASES.items():
        if phase not in existing_phases:
            db.add(ProcessStatus(session_id=session_id, phase=phase, status=status, error=None))
    db.commit()


def update_status(db, session_id, phase, status, error=None):
    process_status = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()

    if process_status is None:
        process_status = ProcessStatus(session_id=session_id, phase=phase)
        db.add(process_status)
        logger.warning(f"No status row found for session={session_id} phase={phase}, creating one")

    process_status.status = status
    process_status.error = error

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"Failed to update status for session={session_id} phase={phase}")
        raise

    logger.info(f"Status for session={session_id} phase={phase} -> {status}")
    return process_status