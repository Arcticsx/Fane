import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..services.utility.getdb import get_db_session
from ..models.rpg_sessions import (
    ChronicleChapter,
    ChronicleMessages,
    RpgSession,
    SourceDocument,
    StoryBeat,
    StoryEvent,
    TurnLog,
)
from ..services.utility.response import get_response
from ..services.documents.vectorstore import query_chroma_for_lore
from ..services.utility.config import DATA_DIR

router = APIRouter(prefix="/story", tags=["chronicle"])
AVATAR_DIR = Path(DATA_DIR) / "images"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@router.get("")
async def list_sessions(db: Session = Depends(get_db_session)):
    sessions = (
        db.query(RpgSession)
        .order_by(RpgSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "synopsis": session.synopsis,
            "genre": session.genre,
            "setup_status": session.setup_status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "avatar": session.avatar,
        }
        for session in sessions
    ]


@router.get("/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db_session)):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "title": session.title,
        "synopsis": session.synopsis,
        "genre": session.genre,
        "magic_rules_md": session.magic_rules_md,
        "setup_status": session.setup_status,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "avatar": session.avatar,
    }


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


class ChronicleChatRequest(BaseModel):
    user_input: str
    chapter_id: Optional[str] = None


@router.post("/{session_id}/chat")
async def chronicle_chat(
    session_id: str,
    body: ChronicleChatRequest,
    db: Session = Depends(get_db_session),
):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    chapter = None
    if body.chapter_id:
        chapter = (
            db.query(ChronicleChapter)
            .filter(
                ChronicleChapter.id == body.chapter_id,
                ChronicleChapter.session_id == session_id,
            )
            .first()
        )
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
    else:
        chapter = (
            db.query(ChronicleChapter)
            .filter(ChronicleChapter.session_id == session_id)
            .order_by(ChronicleChapter.number)
            .first()
        )
        if not chapter:
            chapter = ChronicleChapter(
                id=str(uuid.uuid4()),
                session_id=session_id,
                number=1,
                summary="",
            )
            db.add(chapter)
            db.flush()

    recent_messages = (
        db.query(ChronicleMessages)
        .filter(
            ChronicleMessages.session_id == session_id,
            ChronicleMessages.chapter_id == chapter.id,
        )
        .order_by(ChronicleMessages.created_at.asc())
        .limit(20)
        .all()
    )

    message_history = []
    for message in recent_messages:
        role = message.sender
        if role == "player":
            role = "user"
        elif role == "narrator":
            role = "assistant"
        message_history.append({"role": role, "content": message.content})

    system_prompt = (
        f"You are a chronicle storyteller for an RPG session.\n"
        f"Title: {session.title}\n"
        f"Genre: {session.genre or 'Unknown'}\n"
        f"Synopsis: {session.synopsis or 'No synopsis'}\n"
        f"World Rules: {session.magic_rules_md or 'No special rules'}\n"
        "Respond in character and maintain narrative consistency."
    )

    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(message_history)
        messages.append({"role": "user", "content": body.user_input})
        assistant_response = get_response(messages)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_message = ChronicleMessages(
        id=str(uuid.uuid4()),
        session_id=session_id,
        chapter_id=chapter.id,
        sender="player",
        content=body.user_input,
    )
    assistant_message = ChronicleMessages(
        id=str(uuid.uuid4()),
        session_id=session_id,
        chapter_id=chapter.id,
        sender="narrator",
        content=assistant_response,
    )
    db.add_all([user_message, assistant_message])
    db.commit()

    chat_messages = [
        *message_history,
        {"role": "user", "content": body.user_input},
        {"role": "assistant", "content": assistant_response},
    ]

    return {
        "session_id": session_id,
        "chapter_id": chapter.id,
        "user_input": body.user_input,
        "response": assistant_response,
        "message": assistant_response,
        "messages": chat_messages,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }