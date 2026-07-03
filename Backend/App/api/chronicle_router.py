from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import Optional

try:
    from ..database import get_db
    from ..models.rpg_sessions import RpgSession
    from ..services.ingestion import ingest_pdf_to_session
except ImportError:
    from database import get_db
    from models.rpg_sessions import RpgSession
    from services.ingestion import ingest_pdf_to_session

router = APIRouter(prefix="/story", tags=["chronicle"])


@router.post("")
async def create_session(
    title: str = Form(...),
    synopsis: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    magic_rules_md: Optional[str] = Form(None),
    context_token_limit: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    session = RpgSession(
        title=title,
        synopsis=synopsis,
        genre=genre,
        world_key=world_key,
        magic_rules_md=magic_rules_md,
        context_token_limit=context_token_limit,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "title": session.title,
        "synopsis": session.synopsis,
        "genre": session.genre,
        "created_at": session.created_at.isoformat(),
        "chunks_saved": source_doc.chunk_count if source_doc else 0,
    }