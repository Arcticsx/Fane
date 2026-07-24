import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.services.utility.status import PIPELINE_PHASES

from ..services.utility.getdb import get_db_session
from ..models.rpg_sessions import (
    ChronicleChapter,
    ChronicleMessages,
    ProcessStatus,
    ProcessStep,
    RpgSession,
    SourceDocument,
    StoryBeat,
    StoryEvent,
    TurnLog,
)
from ..services.utility.response import get_response
from ..services.documents.vectorstore import query_chroma_for_lore
from ..services.documents.process_documents import process_document
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
    doc_map = {}
    if sessions:
        docs = db.query(SourceDocument).filter(
            SourceDocument.session_id.in_([s.id for s in sessions])
        ).all()
        doc_map = {d.session_id: d.id for d in docs}
    return [
        {
            "id": session.id,
            "doc_id": doc_map.get(session.id),
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

    doc = db.query(SourceDocument).filter(SourceDocument.session_id == session_id).first()

    return {
        "id": session.id,
        "doc_id": doc.id if doc else None,
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
        "chunks_saved": 0,
    }


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    title: Optional[str] = Form(None),
    synopsis: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    magic_rules_md: Optional[str] = Form(None),
    context_token_limit: Optional[int] = Form(None),
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db_session),
):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if title is not None:
        session.title = title
    if synopsis is not None:
        session.synopsis = synopsis
    if genre is not None:
        session.genre = genre
    if magic_rules_md is not None:
        session.magic_rules_md = magic_rules_md
    if context_token_limit is not None:
        session.context_token_limit = context_token_limit

    if avatar and avatar.filename:
        extension = Path(avatar.filename).suffix or ".png"
        filename = f"chronicle-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{extension}"
        file_path = AVATAR_DIR / filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        session.avatar = f"/data/images/{filename}"

    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "title": session.title,
        "synopsis": session.synopsis,
        "genre": session.genre,
        "magic_rules_md": session.magic_rules_md,
        "context_token_limit": session.context_token_limit,
        "setup_status": session.setup_status,
        "created_at": session.created_at.isoformat(),
        "avatar": session.avatar,
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db_session)):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.delete(session)
    db.commit()

    return {"deleted": True}


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
                title="Chapter 1",
                start_page=1,
                end_page=1,
                page_range="1-1",
                characters=[],
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

    context_blocks = []
    source_documents = (
        db.query(SourceDocument)
        .filter(SourceDocument.session_id == session_id)
        .all()
    )
    for source_document in source_documents:
        if getattr(source_document, "status", None) != "ready":
            continue
        try:
            lore_results = query_chroma_for_lore(session_id, body.user_input, n_results=5)
        except Exception:
            lore_results = []
        if lore_results:
            snippets = [item.get("text", "") for item in lore_results if item.get("text")]
            if snippets:
                context_blocks.append("Relevant PDF content:\n" + "\n".join(snippets))

    context_text = "\n\n".join(context_blocks)
    system_prompt = (
        f"You are a chronicle storyteller for an RPG session.\n"
        f"Title: {session.title}\n"
        f"Genre: {session.genre or 'Unknown'}\n"
        f"Synopsis: {session.synopsis or 'No synopsis'}\n"
        f"World Rules: {session.magic_rules_md or 'No special rules'}\n"
        "Respond in character and maintain narrative consistency."
    )
    if context_text:
        system_prompt = f"{system_prompt}\n\n{context_text}"

    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(message_history)
        messages.append({"role": "user", "content": body.user_input})
        assistant_response = get_response(messages, mode="chat", type="default")
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

    existing_beats = db.query(StoryBeat).filter(StoryBeat.session_id == session_id).count()
    existing_events = db.query(StoryEvent).filter(StoryEvent.session_id == session_id).count()
    if existing_beats == 0:
        db.add(
            StoryBeat(
                id=str(uuid.uuid4()),
                session_id=session_id,
                description=assistant_response,
                status="completed",
                beat_order=1,
                classification="plot_point",
            )
        )
    if existing_events == 0:
        db.add(
            StoryEvent(
                id=str(uuid.uuid4()),
                session_id=session_id,
                description=assistant_response,
                significance="narrative",
            )
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


@router.get("/{session_id}/process-status")
async def get_process_status(session_id: str, db: Session = Depends(get_db_session)):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    PHASE_ORDER = {phase: order for phase, order in PIPELINE_PHASES}

    phases = (
        db.query(ProcessStatus)
        .filter(ProcessStatus.session_id == session_id)
        .all()
    )
    phases.sort(key=lambda ps: PHASE_ORDER.get(ps.phase, 999))

    phase_list = []
    for ps in phases:
        steps = sorted(ps.steps, key=lambda s: s.order)
        phase_list.append({
            "phase": ps.phase,
            "status": ps.status,
            "error": ps.error,
            "started_at": ps.started_at.isoformat() if ps.started_at else None,
            "completed_at": ps.completed_at.isoformat() if ps.completed_at else None,
            "steps": [
                {
                    "step": s.step,
                    "order": s.order,
                    "status": s.status,
                    "error": s.error,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in steps
            ],
        })

    completed_phases = sum(1 for p in phase_list if p["status"] == "completed")

    return {
        "session_id": session_id,
        "total_phases": len(phase_list),
        "completed_phases": completed_phases,
        "phases": phase_list,
    }


@router.post("/{session_id}/retry")
async def retry_chronicle_processing(
    session_id: str,
    db: Session = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    session = db.query(RpgSession).filter(RpgSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    failed_docs = (
        db.query(SourceDocument)
        .filter(
            SourceDocument.session_id == session_id,
            SourceDocument.status == "failed",
        )
        .all()
    )

    if not failed_docs:
        return {"status": "nothing_to_retry", "retried_count": 0}

    retried_count = 0
    for source_doc in failed_docs:
        file_path = source_doc.file_path
        
        if not file_path or not os.path.exists(file_path):
            continue
        
        background_tasks.add_task(
            process_document,
            source_doc_id=source_doc.id,
            session_id=session_id,
            temp_path=file_path,
            filename=source_doc.filename,
        )
        retried_count += 1

    failed_phases = (
        db.query(ProcessStatus)
        .filter(
            ProcessStatus.session_id == session_id,
            ProcessStatus.status == "failed",
        )
        .all()
    )
    for phase in failed_phases:
        phase.status = "pending"
        phase.error = None
        phase.started_at = None
        phase.completed_at = None
    db.commit()

    return {
        "status": "retrying",
        "retried_count": retried_count,
        "message": f"{retried_count} document(s) re-queued for processing.",
    }