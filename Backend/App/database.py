from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

try:
    from .models import Personality
    from .models import Session, Message, Context
    from .models.dbbase import Base
except ImportError:
    from models import Personality
    from models import Session, Message, Context
    from models.dbbase import Base

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .config import BASE_DIR, DATA_DIR



DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "chatbot.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session():
    """FastAPI dependency: yields an actual Session (use with Depends)."""
    with get_db() as db:
        yield db


def get_db_session():
    """FastAPI dependency: yields an actual Session (use with Depends)."""
    with get_db() as db:
        yield db

def init_db():
    """Initialize database tables and add any missing columns for older databases."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        inspector = inspect(conn)
        if 'rpg_sessions' not in inspector.get_table_names():
            return

        columns = {column['name'] for column in inspector.get_columns('rpg_sessions')}
        if 'avatar' not in columns:
            conn.execute(text('ALTER TABLE rpg_sessions ADD COLUMN avatar VARCHAR'))

def get_sessions(db, persona_key: str):
    rows = (
        db.query(Session)
        .filter(Session.persona_key == persona_key)
        .order_by(Session.updated_at.desc())
        .all()
    )
    results = []
    for s in rows:
        # Get last user message for preview
        last_msg = (
            db.query(Message)
            .filter(Message.session_id == s.id, Message.sender == "user")
            .order_by(Message.id.desc())
            .first()
        )
        preview = last_msg.content[:80] + "..." if last_msg else "No messages yet"
        results.append({
            "id": s.id,
            "persona_key": s.persona_key,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "preview": preview
        })
    return results

def get_recent_sessions(db):
    sessions = (
        db.query(Session)
        .order_by(Session.updated_at.desc())
        .limit(10)
        .all()
    )
    results = []
    for s in sessions:
        personality = (
            db.query(Personality)
            .filter(Personality.key == s.persona_key)
            .first()
        )
        last_message = (
            db.query(Message)
            .filter(
                Message.session_id == s.id,
                Message.sender == "user"
            )
            .order_by(Message.id.desc())
            .first()
        )
        results.append({
            "id": s.id,
            "persona_key": s.persona_key,
            "persona_id": s.persona_id,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "persona_name": personality.name if personality else None,
            "persona_avatar": personality.avatar if personality else None,
            "last_user_message": (
                last_message.content if last_message else None
            )
        })
    return results

def get_session_by_index(db, persona_key, index: int, persona_id=None):
    row = (
        db.query(Session)
        .filter(Session.persona_key == persona_key)
        .order_by(Session.updated_at.desc())
        .offset(index)
        .limit(1)
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "persona_key": row.persona_key,
        "persona_id": row.persona_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

_NO_SESSION = object()

def load_session(db, persona, system_message, session=_NO_SESSION):
    # If caller provided the `session` argument (even if it's None), treat as
    # router usage and return (context, full_messages). If the caller omitted
    # the argument (CLI usage), return (context, full_messages, session_obj).
    if session is not _NO_SESSION:
        if session:
            session_id = session["id"]
            rows = (
                db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.id.asc())
                .all()
            )
            context_rows = (
                db.query(Context)
                .filter(Context.session_id == session_id)
                .order_by(Context.id.asc())
                .all()
            )
            full_messages = [system_message]
            for row in rows:
                if row.sender == "system":
                    continue
                full_messages.append({"id": row.id, "role": row.sender, "content": row.content})
            context = [system_message]
            for row in context_rows:
                if row.sender == "system":
                    continue
                context.append({"id": row.id, "role": row.sender, "content": row.content})
            return context, full_messages

        first_msg = persona.get("opening_prompt", "Introduce yourself and start the conversation.")
        full_messages = [system_message, {"role": "assistant", "content": first_msg}]
        context = [system_message.copy(), {"role": "assistant", "content": first_msg}]
        return context, full_messages

    # CLI caller (no session argument provided): return triple including session placeholder
    first_msg = persona.get("opening_prompt", "Introduce yourself and start the conversation.")
    full_messages = [system_message, {"role": "assistant", "content": first_msg}]
    context = [system_message.copy(), {"role": "assistant", "content": first_msg}]
    return context, full_messages, None

def save_session(db, persona_key, messages=None, context=None, session_id=None):
    if messages is None:
        messages = []
    if context is None:
        context = []
    non_system_messages = [m for m in messages if m.get("role") != "system"]
    non_system_context = [m for m in context if m.get("role") != "system"]
    if not non_system_messages and not non_system_context:
        return None
    now = datetime.now(timezone.utc).isoformat()
    if session_id:
        db.query(Session).filter(Session.id == session_id).update(
            {"persona_key": persona_key, "updated_at": now}
        )
        db.query(Message).filter(Message.session_id == session_id).delete()
        db.query(Context).filter(Context.session_id == session_id).delete()
    else:
        new_session = Session(
            persona_key=persona_key, created_at=now, updated_at=now
        )
        db.add(new_session)
        db.flush()
        session_id = new_session.id
    for msg in non_system_messages:
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        db.add(Message(session_id=session_id, sender=role, content=content))
    for msg in non_system_context:
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        db.add(Context(session_id=session_id, sender=role, content=content))
    print(f"Session {session_id} saved.")
    return session_id

def delete_session(db, session_id):
    if not session_id:
        return False
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.query(Context).filter(Context.session_id == session_id).delete()
    db.query(Session).filter(Session.id == session_id).delete()
    return True