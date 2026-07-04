from fastapi import (
    APIRouter,
    HTTPException,
    Form,
    File,
    UploadFile,
    FastAPI,
    Depends
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from personalities import (
    get_personalities,
    create_personality,
    update_personality,
    delete_personality,
    pick_personality,
)
from database import save_session, load_session, get_session_by_index, get_sessions, delete_session, DATA_DIR, init_db, get_db 
from response import get_response
from personalities import init_personalities_db
from memory import trim_memory
from config import textPrompt
import os
import shutil
import sqlite3
from uuid import uuid4
from pathlib import Path

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
AVATAR_DIR = Path(DATA_DIR) / "images"

os.makedirs(AVATAR_DIR, exist_ok=True)

# Mount static files to serve images
app.mount("/data/images", StaticFiles(directory=str(AVATAR_DIR)), name="images")

init_db()
init_personalities_db()

def db_dependency():
    with get_db() as conn:
        yield conn


#------------------PERSONALITIES----------------------


@app.get("/personalities")
def list_personalities():
    return get_personalities()


@app.post("/personalities", status_code=201)
async def create_persona(
    name: str = Form(...),
    description: str = Form(None),
    system: str = Form(...),
    scenario: str = Form(...),
    opening_prompt: str = Form(...),
    avatar: UploadFile = File(None)
):
    avatar_rel_path = None

    if avatar:
        # Keep unique filename
        extension = avatar.filename.split(".")[-1]
        filename = f"{uuid4()}.{extension}"

        # Store file in Data/images/
        file_path = AVATAR_DIR / filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        
        # Return URL path for frontend to access
        avatar_rel_path = f"/data/images/{filename}"

    return create_personality(
        name=name,
        description=description,
        system=system,
        scenario=scenario,
        opening_prompt=opening_prompt,
        avatar=avatar_rel_path
    )


@app.put("/personalities/{persona_key}")
async def update_persona(
    persona_key: str,
    name: str = Form(...),
    description: str = Form(None),
    system: str = Form(...),
    scenario: str = Form(...),
    opening_prompt: str = Form(...),
    avatar: UploadFile = File(None)
):
    avatar_rel_path = None

    if avatar:
        extension = avatar.filename.split(".")[-1]
        filename = f"{uuid4()}.{extension}"

        # Store file in Data/images/
        file_path = AVATAR_DIR / filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        
        # Return URL path for frontend to access
        avatar_rel_path = f"/data/images/{filename}"

    updated = update_personality(
        persona_key,
        name,
        description,
        system,
        scenario,
        opening_prompt,
        avatar_rel_path,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Persona not found."
        )

    return updated

@app.delete("/personalities/{persona_key}")
def delete_persona(persona_key: str):
    deleted = delete_personality(persona_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found.")
    return {"deleted": True}

class PickPersonaRequest(BaseModel):
    choice: str

@app.post("/personalities/pick")
def pick_persona(body: PickPersonaRequest):
    result = pick_personality(body.choice)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="No personalities exist or choice was 'n'. POST /personalities to create one."
        )
    return result


#------------------SESSIONS----------------------
@app.get("/sessions/{persona_name}")
def list_sessions(persona_name: str, conn: sqlite3.Connection = Depends(db_dependency)):
    """Get the last 5 sessions for a persona."""
    sessions = get_sessions(conn, persona_name)
    if not sessions:
        return {"sessions": [], "message": "No previous sessions found."}
    return {"sessions": sessions}


@app.delete("/sessions/{persona_name}/{session_id}")
def delete_session_endpoint(persona_name: str, session_id: int, conn: sqlite3.Connection = Depends(db_dependency)):
    deleted = delete_session(conn, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True}


class PickSessionRequest(BaseModel):
    persona_name: str
    index: int | None = None  # None = start new session

@app.post("/sessions/pick")
def pick_session_endpoint(body: PickSessionRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Pick a session by index, or pass null index to start a new one."""
    if body.index is None:
        return {"session": None, "new": True}

    session = get_session_by_index(conn, body.persona_name, body.index - 1)  # 1-based
    if not session:
        return {"session": None, "new": True, "warning": "Index out of range, starting new session."}

    return {"session": session, "new": False}

class SessionData(BaseModel):
    id: int
    persona: str
    created_at: str
    updated_at: str

class LoadSessionRequest(BaseModel):
    persona_key: str
    session: SessionData | None = None  # pass null to start fresh
    

@app.post("/sessions/load")
def load(body: LoadSessionRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    personalities = get_personalities()
    persona = personalities.get(body.persona_key)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")

    template = f"{persona.get('system','')}\n\n{textPrompt}\n\nScenario: {persona.get('Scenario','')}"
    system_message = {"role": "system", "content": template}

    # Convert Pydantic model to dict if session exists
    session_dict = body.session.model_dump() if body.session else None
    context, full_messages = load_session(conn, persona, system_message, session_dict)
    
    # Remove id field from messages for clean response
    clean_messages = [{k: v for k, v in m.items() if k != "id"} for m in full_messages]
    clean_context = [{k: v for k, v in m.items() if k != "id"} for m in context]

    return {
        "session": session_dict,
        "messages": clean_messages,
        "context": clean_context,
        "resumed": body.session is not None
    }

class Message(BaseModel):
    role: str
    content: str

class SaveSessionRequest(BaseModel):
    persona_key: str
    messages: list[dict]
    context: list[dict]
    session_id: int | None = None

@app.post("/sessions/save")
def save(body: SaveSessionRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    personalities = get_personalities()
    persona = personalities.get(body.persona_key)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")

    session_id = save_session(conn, persona["name"], body.messages, body.context, body.session_id)
    if session_id is None:
        raise HTTPException(status_code=400, detail="No messages to save.")
    return {"saved": True, "session_id": session_id}

    
# ── Chat ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    persona_key: str
    messages: list[dict]        
    context: list[dict]   
    session_id: int | None = None
    user_input: str

@app.post("/chat")
def chat(body: ChatRequest):
    personalities = get_personalities()
    persona = personalities.get(body.persona_key)
    
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")
    
    template = f"{persona.get('system','')}\n\n{textPrompt}\n\nScenario: {persona.get('Scenario','')}"
    system_message = {"role": "system", "content": template}

    messages = body.messages + [{"role": "user", "content": body.user_input}]

    try:
        assistant_msg = get_response(messages)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    
    messages.append({"role": "assistant", "content": assistant_msg})
    messages = trim_memory(messages, system_message)

    # Update full context history
    msg_id = max((m.get("id", 0) for m in body.context), default=0)
    context = body.context + [
        {"id": msg_id + 1, "role": "user",      "content": body.user_input},
        {"id": msg_id + 2, "role": "assistant",  "content": assistant_msg},
    ]

    return {
        "assistant_message": assistant_msg,
        "messages": messages,
        "context": context,
    }
