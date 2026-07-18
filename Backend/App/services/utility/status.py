from datetime import datetime, timezone
import logging

from .getdb import get_db
from ...models.rpg_sessions import ProcessStatus, ProcessStep

logger = logging.getLogger(__name__)

PIPELINE_PHASES = [
    ("document_upload",        0),
    ("metadata_extraction",    1),
    ("chapter_extraction",     2),
    ("vector_storage",         3),
    ("story_beats",            4),
    ("entity_extraction",      5),
    ("character_processing",   6),
]

PHASE_STEPS = {
    "story_beats": [
        ("beats_extract",         600),
        ("beats_save_candidates", 601),
        ("beats_reduce",          602),
        ("beats_save_reduced",    603),
        ("beats_graph",           604),
    ],
    "entity_extraction": [
        ("entities_extract",      700),
        ("entities_merge",        701),
        ("entities_separate",     702),
    ],
    "character_processing": [
        ("characters_classify",    800),
        ("characters_persist",     801),
        ("characters_segment",     802),
        ("characters_arc",     803),
    ],
}

def _now():
    return datetime.now(timezone.utc)


def init_pipeline_phases(db, session_id):
    existing_phases = {
        row.phase for row in
        db.query(ProcessStatus.phase).filter_by(session_id=session_id).all()
    }
    for phase, order in PIPELINE_PHASES:
        if phase not in existing_phases:
            ps = ProcessStatus(session_id=session_id, phase=phase, status="pending")
            db.add(ps)
            db.flush()
            if phase not in PHASE_STEPS:
                db.add(ProcessStep(
                    session_id=session_id,
                    phase=phase,
                    step=phase,
                    order=order,
                    status="pending",
                    process_status_id=ps.id,
                ))

    for phase, steps in PHASE_STEPS.items():
        ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()
        if not ps:
            continue
        existing_step_names = {
            row.step for row in
            db.query(ProcessStep.step).filter_by(session_id=session_id, phase=phase).all()
        }
        for step_name, step_order in steps:
            if step_name not in existing_step_names:
                db.add(ProcessStep(
                    session_id=session_id,
                    phase=phase,
                    step=step_name,
                    order=step_order,
                    status="pending",
                    process_status_id=ps.id,
                ))

    db.commit()


def get_next_pending_step(db, session_id):
    step = db.query(ProcessStep).filter(
        ProcessStep.session_id == session_id,
        ProcessStep.status != "completed",
    ).order_by(ProcessStep.order).first()

    if not step:
        return None

    if step.status in ("failed", "processing"):
        step.status = "pending"
        step.error = None
        ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=step.phase).first()
        if ps:
            ps.status = "pending"
            ps.error = None
        db.commit()

    return step.phase, step.step


def is_step_completed(db, session_id, phase, step_name):
    step = db.query(ProcessStep).filter_by(
        session_id=session_id, phase=phase, step=step_name, status="completed",
    ).first()
    return step is not None


def start_step(db, session_id, phase, step_name):
    ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()
    if ps:
        ps.status = "processing"
        ps.started_at = _now()

    step = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase, step=step_name).first()
    if step:
        step.status = "processing"
        step.started_at = _now()
    db.commit()


def complete_step(db, session_id, phase, step_name):
    step = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase, step=step_name).first()
    if step:
        step.status = "completed"
        step.completed_at = _now()
    db.commit()

    _sync_phase_status_from_steps(db, session_id, phase)


def _sync_phase_status_from_steps(db, session_id, phase):
    """If all ProcessSteps for a phase are completed, mark the ProcessStatus as completed."""
    total = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase).count()
    done = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase, status="completed").count()
    if total > 0 and total == done:
        ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()
        if ps and ps.status != "completed":
            ps.status = "completed"
            ps.completed_at = _now()
            db.commit()


def fail_step(db, session_id, phase, step_name, error=None):
    error_str = str(error)[:1000] if error else None

    ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()
    if ps:
        ps.status = "failed"
        ps.error = error_str

    step = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase, step=step_name).first()
    if step:
        step.status = "failed"
        step.error = error_str
    db.commit()


def initialize_status(db, session_id):
    """Legacy wrapper — calls init_pipeline_phases."""
    init_pipeline_phases(db, session_id)


def update_status(db, session_id, phase, status, error=None):
    """Legacy wrapper — upserts a single ProcessStatus row by session_id + phase."""
    ps = db.query(ProcessStatus).filter_by(session_id=session_id, phase=phase).first()
    if ps is None:
        ps = ProcessStatus(session_id=session_id, phase=phase, status=status)
        db.add(ps)
        db.flush()
        logger.warning(f"No status row found for session={session_id} phase={phase}, creating one")

    ps.status = status
    ps.error = error
    if status in ("processing",):
        ps.started_at = ps.started_at or _now()
    if status in ("completed", "failed"):
        ps.completed_at = _now()

    step = db.query(ProcessStep).filter_by(session_id=session_id, phase=phase, step=phase).first()
    if step:
        step.status = status
        step.error = error
        if status in ("processing",):
            step.started_at = step.started_at or _now()
        if status in ("completed", "failed"):
            step.completed_at = _now()

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"Failed to update status for session={session_id} phase={phase}")
        raise
    logger.info(f"Status for session={session_id} phase={phase} -> {status}")
    return ps
