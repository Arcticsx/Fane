from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from Backend.App.models.dbbase import Base

from .config import DATA_DIR

DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "chatbot.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db_session():
    """FastAPI dependency: yields an actual Session (use with Depends)."""
    with get_db() as db:
        yield db

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