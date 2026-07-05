from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.rpg_sessions import RpgSession
from ..services.ingestion import ingest_pdf_to_session
from ..services.chronicle_session import create_session

router = APIRouter(prefix="/story", tags=["chronicle"])


@router.post("")
async def create_session(
    title: str = Form(...),
    synopsis: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    magic_rules_md: Optional[str] = Form(None),
    context_token_limit: Optional[int] = Form(None),
):
    session = create_session(title, synopsis, genre, magic_rules_md, context_token_limit)

    return {
        "id": session.id,
        "title": session.title,
        "synopsis": session.synopsis,
        "genre": session.genre,
        "created_at": session.created_at.isoformat(),
        "chunks_saved": source_doc.chunk_count if source_doc else 0,
    }
    
    