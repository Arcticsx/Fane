# Architecture

## System Overview

Fane is a full-stack AI roleplay and chronicle storytelling application with two main modes:

1. **Persona Chat** -- Conversations with customizable AI characters, persistent sessions, and automatic memory management.
2. **Chronicle System** -- A document-processing pipeline that ingests PDFs (e.g., novels), extracts story beats, characters, and lore entities, then builds a vector-indexed knowledge base for RAG-powered narrative chat.

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│              React 18 + Vite + Tailwind CSS 4                │
│                                                              │
│  PersonalitySelector ──► SessionSelector ──► Chat            │
│  ChronicleCreator ──► ChronicleSelector ──► ChronicleChat   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (fetch)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                           │
│                                                              │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ chat_router   │  │ chronicle_router  │  │documents_router│ │
│  │ /personalities│  │ /story            │  │ /story/{id}/  │  │
│  │ /sessions     │  │ /story/{id}/chat  │  │   docs        │  │
│  │ /chat         │  │ /story/{id}/      │  └───────────────┘  │
│  └──────────────┘  │   process-status  │                     │
│                    └──────────────────┘                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Services Layer                        │   │
│  │  chat/        │ utility/     │ documents/ │ beats/    │   │
│  │  database     │ config       │ documents  │ extraction│   │
│  │  memory       │ response     │ vectorstore│ graph     │   │
│  │  personalities│ getdb        │ ingestion  │ entities/ │   │
│  │               │ status       │ process    │ characters│   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Data Layer                            │   │
│  │  SQLite (SQLAlchemy ORM)  │  ChromaDB (vectors)       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐   ┌─────────┐   ┌──────────┐
     │ Ollama  │   │ OpenAI  │   │Anthropic │  ...
     │ (local) │   │         │   │          │
     └─────────┘   └─────────┘   └──────────┘
```

## Backend Structure

```
Backend/
├── App/
│   ├── api/
│   │   ├── chat_router.py        # Main FastAPI app, personality/session/chat endpoints
│   │   ├── chronicle_router.py   # Chronicle CRUD + chat endpoints
│   │   └── documents_router.py   # PDF upload + processing status endpoints
│   ├── models/
│   │   ├── dbbase.py             # SQLAlchemy declarative_base()
│   │   ├── models.py             # Chat domain: Personality, Session, Message, Context
│   │   └── rpg_sessions.py       # Chronicle domain: 17 tables (RpgSession, StoryBeat, Character, etc.)
│   ├── services/
│   │   ├── chat/                 # Personality CRUD, session management, memory trimming
│   │   ├── utility/              # Config, DB engine, LLM client, pipeline status
│   │   ├── documents/            # PDF conversion, chunking, embedding, ChromaDB
│   │   ├── beats/                # Story beat extraction, reduction, graph construction
│   │   └── entities/             # Entity extraction, character/lore processing
│   └── main.py                   # Entry point (uvicorn bootstrap)
├── data/                         # SQLite DB, ChromaDB, uploaded files, avatar images
└── tests/                        # pytest test suite
```

### Key Design Decisions

- **SQLite** for simplicity -- single-file database, no external dependencies.
- **ChromaDB** for vector storage -- persistent local collections per session.
- **LangChain** as the LLM abstraction layer -- unified interface across 6 providers.
- **Background tasks** for document processing -- FastAPI `BackgroundTasks` with heartbeat-based crash detection.
- **Pydantic models** for request/response validation on all API endpoints.

## Data Flow: Persona Chat

```
1. User types message in Chat component
2. Frontend sends POST /chat {persona_key, messages, context, user_input}
3. Backend:
   a. Loads persona system prompt + global textPrompt + scenario
   b. Appends user message to messages list
   c. Calls LLM via get_response(messages, mode="chat")
   d. If >10 non-system messages, trim_memory() summarizes older ones
   e. Returns {assistant_message, messages, context}
4. Frontend auto-saves via POST /sessions/save
```

## Data Flow: Chronicle Processing

```
1. User creates chronicle + uploads PDF
2. Frontend sends POST /story (create RpgSession) + POST /story/{id}/docs (upload PDF)
3. Backend triggers background task: process_document()
   Phase 1 - Documents: metadata extraction → chapter extraction → chunk/embed → ChromaDB
   Phase 2 - Beats: windowed extraction → reduction → save → graph construction
   Phase 3 - Entities: extraction → merge → separate (characters vs lore) → classify → segment → arc analysis
4. Frontend polls GET /story/{id}/docs/{doc_id}/status until ready
```

## Data Flow: Chronicle Chat

```
1. User types message in ChronicleChat component
2. Frontend sends POST /story/{session_id}/chat {user_input}
3. Backend:
   a. Loads recent 20 messages for the chapter
   b. Queries ChromaDB for relevant PDF snippets (RAG)
   c. Builds system prompt with session metadata + RAG context
   d. Calls LLM
   e. Persists user + narrator messages to chronicle_messages
   f. Creates initial StoryBeat/StoryEvent if none exist
   g. Returns response + full message history
```

## LLM Provider Abstraction

The `response.py` service provides a unified interface across six providers:

| Provider | Model Format | Example |
|----------|-------------|---------|
| Ollama | `ollama:model` | `ollama:qwen2.5:7b` |
| OpenAI | `openai:model` | `openai:gpt-4o-mini` |
| Anthropic | `anthropic:model` | `anthropic:claude-3-5-sonnet` |
| DeepSeek | `deepseek:model` | `deepseek:deepseek-chat` |
| Gemini | `gemini:model` | `gemini:gemini-pro` |
| Grok | `grok:model` | `grok:grok-beta` |

Each provider builder returns a LangChain chat model instance. Structured output is supported via JSON schemas passed to the model constructor. Retry logic with exponential backoff handles transient errors (429, 500, 502, 503).

## Frontend Architecture

- **React 18** with **React Router 7** for client-side routing
- **Vite 6** for development and bundling
- **Tailwind CSS 4** for styling
- **No state management library** -- local component state + prop drilling
- **Theme system** with 8 built-in themes + custom theme creation, persisted to localStorage
- **API client** (`api.js`) -- centralized fetch wrapper with error handling

See [frontend-guide.md](frontend-guide.md) for component details.
