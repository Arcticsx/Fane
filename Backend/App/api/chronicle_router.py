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


# ── Request Models ──────────────────────────────────────────
class ChronicleChainRequest(BaseModel):
    """Request model for chronicle chat/chain interactions"""
    user_input: str
    chapter_id: Optional[str] = None


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


@router.post("/{session_id}/chat")
async def chronicle_chat(
    session_id: str,
    body: ChronicleChainRequest,
    db: Session = Depends(get_db_session),
):
    """Handle chat messages for a chronicle session"""
    
    # Fetch the session
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get or create chapter (use first chapter or provided one)
    if body.chapter_id:
        chapter = db.query(ChronicleChapter).filter(
            ChronicleChapter.id == body.chapter_id,
            ChronicleChapter.session_id == session_id
        ).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
    else:
        chapter = db.query(ChronicleChapter).filter(
            ChronicleChapter.session_id == session_id
        ).order_by(ChronicleChapter.number).first()
        if not chapter:
            raise HTTPException(status_code=400, detail="No chapters found for this session")
    
    # Fetch recent messages for context
    recent_messages = db.query(ChronicleMessages).filter(
        ChronicleMessages.session_id == session_id,
        ChronicleMessages.chapter_id == chapter.id
    ).order_by(ChronicleMessages.created_at.desc()).limit(10).all()
    
    # Build message history in conversation order
    message_history = [
        {"role": m.sender, "content": m.content}
        for m in reversed(recent_messages)
    ]
    
    # Build system prompt with session context
    system_prompt = f"""You are a chronicle storyteller for an RPG session.
Title: {session.title}
Genre: {session.genre}
Setting: {session.synopsis or 'Unknown'}
World Rules: {session.magic_rules_md or 'No special rules'}

Respond in character, maintaining narrative consistency."""
    
    # Get AI response
    try:
        messages = [{"role": "system", "content": system_prompt}] + message_history + [
            {"role": "user", "content": body.user_input}
        ]
        assistant_response = get_response(messages)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    # Store user message
    user_msg = ChronicleMessages(
        id=str(re.sub(r'[^a-zA-Z0-9-]', '', str(datetime.now(timezone.utc)))),
        session_id=session_id,
        chapter_id=chapter.id,
        sender="player",
        content=body.user_input,
    )
    db.add(user_msg)
    db.flush()
    
    # Store assistant response
    assistant_msg = ChronicleMessages(
        id=str(re.sub(r'[^a-zA-Z0-9-]', '', str(datetime.now(timezone.utc)))) + "_ai",
        session_id=session_id,
        chapter_id=chapter.id,
        sender="narrator",
        content=assistant_response,
    )
    db.add(assistant_msg)
    db.commit()
    
    return {
        "session_id": session_id,
        "chapter_id": chapter.id,
        "user_input": body.user_input,
        "response": assistant_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }