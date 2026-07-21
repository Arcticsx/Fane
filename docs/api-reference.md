# API Reference

**Base URL:** `http://localhost:8000`

**CORS Origins:** `http://localhost:3000`, `http://localhost:3001`, `http://localhost:5173` (and `127.0.0.1` variants)

**Content Types:**
- JSON endpoints accept `application/json`
- File upload endpoints accept `multipart/form-data`

---

## Personality Endpoints

### List Personalities

```
GET /personalities
```

Returns all personalities as an object keyed by `key`.

**Response:**
```json
{
  "my-character": {
    "id": 1,
    "key": "my-character",
    "name": "My Character",
    "description": "A brave adventurer",
    "system": "You are...",
    "scenario": "In a tavern...",
    "opening_prompt": "Hello traveler...",
    "avatar": "/data/images/abc123.png"
  }
}
```

### Create Personality

```
POST /personalities
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name |
| `description` | string | No | Short description |
| `system` | string | Yes | System prompt for the LLM |
| `scenario` | string | Yes | Scenario context |
| `opening_prompt` | string | Yes | First message shown to user |
| `avatar` | file | No | Avatar image |

**Response (201):**
```json
{
  "id": 1,
  "key": "my-character",
  "name": "My Character",
  ...
}
```

### Update Personality

```
PUT /personalities/{persona_key}
Content-Type: multipart/form-data
```

Same fields as Create. Returns updated personality or `404`.

### Delete Personality

```
DELETE /personalities/{persona_key}
```

**Response:**
```json
{ "deleted": true }
```

Returns `404` if not found.

### Pick Personality

```
POST /personalities/pick
Content-Type: application/json
```

**Request:**
```json
{ "persona_key": "my-character" }
```

Returns the personality object or `400` if not found.

---

## Session Endpoints

### List Recent Sessions

```
GET /sessions/recent
```

Returns the last 10 sessions across all personas.

**Response:**
```json
{
  "sessions": [
    {
      "id": 1,
      "persona_key": "my-character",
      "persona_name": "My Character",
      "avatar": "/data/images/abc.png",
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T01:00:00",
      "last_message": "Hello traveler..."
    }
  ]
}
```

### List Sessions for a Persona

```
GET /sessions/{persona_key}
```

Returns all sessions for the given persona with last-message previews.

### Delete Session

```
DELETE /sessions/{persona_key}/{session_id}
```

**Response:**
```json
{ "deleted": true }
```

### Pick Session

```
POST /sessions/pick
Content-Type: application/json
```

**Request:**
```json
{ "persona_key": "my-character", "index": 1 }
```

**Response:**
```json
{
  "session": { "id": 1, "persona_key": "my-character", ... },
  "new": false
}
```

If `index` is `null` or out of range, returns `{ "session": null, "new": true }`.

### Load Session

```
POST /sessions/load
Content-Type: application/json
```

**Request:**
```json
{
  "persona_key": "my-character",
  "session": { "id": 1, "persona_key": "my-character" }
}
```

Set `session` to `null` for a new session.

**Response:**
```json
{
  "session": { "id": 1, ... },
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "assistant", "content": "Opening prompt..." }
  ],
  "context": [
    { "role": "assistant", "content": "Opening prompt..." }
  ],
  "resumed": false,
  "persona_name": "My Character",
  "persona_key": "my-character"
}
```

### Save Session

```
POST /sessions/save
Content-Type: application/json
```

**Request:**
```json
{
  "persona_key": "my-character",
  "messages": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi there!" }
  ],
  "context": [
    { "id": 1, "role": "user", "content": "Hello" },
    { "id": 2, "role": "assistant", "content": "Hi there!" }
  ],
  "session_id": 1
}
```

Set `session_id` to `null` to create a new session.

**Response:**
```json
{ "saved": true, "session_id": 1 }
```

---

## Chat Endpoint

### Send Chat Message

```
POST /chat
Content-Type: application/json
```

**Request:**
```json
{
  "persona_key": "my-character",
  "messages": [
    { "role": "system", "content": "You are..." },
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi traveler!" }
  ],
  "context": [
    { "id": 1, "role": "user", "content": "Hello" },
    { "id": 2, "role": "assistant", "content": "Hi traveler!" }
  ],
  "session_id": 1,
  "user_input": "What's your name?"
}
```

**Response:**
```json
{
  "assistant_message": "I am Lyra, keeper of the ancient scrolls.",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi traveler!" },
    { "role": "user", "content": "What's your name?" },
    { "role": "assistant", "content": "I am Lyra, keeper of the ancient scrolls." }
  ],
  "context": [
    { "id": 1, "role": "user", "content": "Hello" },
    { "id": 2, "role": "assistant", "content": "Hi traveler!" },
    { "id": 3, "role": "user", "content": "What's your name?" },
    { "id": 4, "role": "assistant", "content": "I am Lyra, keeper of the ancient scrolls." }
  ]
}
```

---

## Chronicle Endpoints

### List Chronicles

```
GET /story
```

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "The Lost Kingdom",
    "synopsis": "A fantasy adventure...",
    "genre": "fantasy",
    "setup_status": "completed",
    "created_at": "2025-01-01T00:00:00",
    "avatar": "/data/images/chronicle-abc.png"
  }
]
```

### Get Chronicle

```
GET /story/{session_id}
```

Returns full chronicle details including `magic_rules_md`.

### Create Chronicle

```
POST /story
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Chronicle title |
| `synopsis` | string | No | Story synopsis |
| `genre` | string | No | Genre (e.g., "fantasy", "sci-fi") |
| `magic_rules_md` | string | No | World rules in Markdown |
| `context_token_limit` | integer | No | Token limit for context |
| `avatar` | file | No | Chronicle avatar image |

**Response (201):**
```json
{
  "id": "uuid",
  "title": "The Lost Kingdom",
  "synopsis": "...",
  "genre": "fantasy",
  "setup_status": "not_started",
  "created_at": "2025-01-01T00:00:00",
  "avatar": null,
  "chunks_saved": 0
}
```

### Update Chronicle

```
PUT /story/{session_id}
Content-Type: multipart/form-data
```

All fields optional. Only provided fields are updated.

### Delete Chronicle

```
DELETE /story/{session_id}
```

**Response:**
```json
{ "deleted": true }
```

### Chronicle Chat

```
POST /story/{session_id}/chat
Content-Type: application/json
```

**Request:**
```json
{ "user_input": "I enter the ancient temple." }
```

**Response:**
```json
{
  "session_id": "uuid",
  "chapter_id": "uuid",
  "user_input": "I enter the ancient temple.",
  "response": "The air grows cold as you step through the crumbling archway...",
  "message": "The air grows cold as you step through the crumbling archway...",
  "messages": [
    { "role": "user", "content": "I enter the ancient temple." },
    { "role": "assistant", "content": "The air grows cold as you step through the crumbling archway..." }
  ],
  "timestamp": "2025-01-01T00:00:00"
}
```

### Get Processing Status

```
GET /story/{session_id}/process-status
```

**Response:**
```json
{
  "session_id": "uuid",
  "total_phases": 7,
  "completed_phases": 4,
  "phases": [
    {
      "phase": "document_upload",
      "status": "completed",
      "error": null,
      "started_at": "2025-01-01T00:00:00",
      "completed_at": "2025-01-01T00:00:01",
      "steps": []
    }
  ]
}
```

---

## Document Endpoints

### Upload Document

```
POST /story/{id}/docs
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | PDF file to upload |

**Response:**
```json
{
  "status": "processing",
  "session_id": "uuid",
  "source_document_id": "uuid",
  "filename": "book.pdf",
  "file_path": "/path/to/saved/file.pdf",
  "file_url": "/data/files/file.pdf",
  "message": "Document is being processed in the background."
}
```

Processing runs asynchronously. Poll the status endpoint to track progress.

### Get Document Status

```
GET /story/{id}/docs/{doc_id}/status
```

**Response:**
```json
{
  "source_document_id": "uuid",
  "status": "processing",
  "chunk_count": 0,
  "error_message": null
}
```

Status values: `pending`, `processing`, `ready`, `failed`.

If the heartbeat has not been updated for 5 minutes, the status automatically changes to `failed` with error `"Server crashed"`.

### Retry Document Processing

```
POST /story/{id}/docs/{doc_id}/retry
```

Retries processing for failed or pending documents.

**Response:**
```json
{
  "status": "retrying",
  "source_document_id": "uuid",
  "session_id": "uuid",
  "message": "Document processing has been re-queued."
}
```

Returns `already_completed` if the document is already processed.

---

## Pydantic Models

### ChatRequest

```python
persona_key: str
messages: list[dict]
context: list[dict]
session_id: int | None
user_input: str
```

### SaveSessionRequest

```python
persona_key: str
messages: list[dict]
context: list[dict]
session_id: int | None
```

### LoadSessionRequest

```python
persona_key: str | None
session: SessionData | None
```

### SessionData

```python
id: int
persona_key: str | None
created_at: str | None
updated_at: str | None
```

### ChronicleChatRequest

```python
user_input: str
chapter_id: str | None
```
