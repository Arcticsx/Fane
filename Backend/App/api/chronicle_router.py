import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db_session
from ..models.rpg_sessions import RpgSession
from ..response import get_response
from ..models.rpg_sessions import ChronicleMessages
from ..models.rpg_sessions import ChronicleChapter, SourceDocument, StoryBeat, StoryEvent, TurnLog
from ..services.vectorstore import query_chroma_for_lore
from ..config import DATA_DIR

router = APIRouter(prefix="/story", tags=["chronicle"])
AVATAR_DIR = Path(DATA_DIR) / "images"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@router.post("")
async def create_session(
    title: str = Form(...),
    synopsis: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    magic_rules_md: Optional[str] = Form(None),
    context_token_limit: Optional[int] = Form(None),
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db_session),        # ← changed
):
    avatar_rel_path = None
    if avatar and avatar.filename:
        extension = Path(avatar.filename).suffix or ".png"
        filename = f"chronicle-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{extension}"
        file_path = AVATAR_DIR / filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        avatar_rel_path = f"/data/images/{filename}"

    session = RpgSession(
        title=title,
        synopsis=synopsis,
        genre=genre,
        magic_rules_md=magic_rules_md,
        context_token_limit=context_token_limit,
        avatar=avatar_rel_path,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "title": session.title,
        "synopsis": session.synopsis,
        "genre": session.genre,
        "setup_status": session.setup_status,
        "created_at": session.created_at.isoformat(),
        "avatar": avatar_rel_path,
    }