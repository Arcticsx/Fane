# Setup & Installation

## Prerequisites

- **Python 3.11+** (tested on 3.13)
- **Node.js 18+** and npm
- **API key** for your chosen LLM provider (or Ollama running locally)

## 1. Clone and Set Up Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
PROVIDER=ollama
MODEL_NAME=qwen2.5:7b
API_KEY=
EMBEDDING_MODEL=thenlper/gte-small
```

### Environment Variables Reference

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `PROVIDER` | Yes | LLM provider: `ollama`, `openai`, `anthropic`, `deepseek`, `gemini`, `grok` | None (stub client) |
| `MODEL_NAME` | Yes | Model identifier for the chosen provider | None |
| `API_KEY` | Yes* | API key for the provider (*not needed for local Ollama) | Empty |
| `EMBEDDING_MODEL` | No | SentenceTransformer model for document embeddings | None |
| `VITE_API_URL` | No | Frontend API base URL (set in frontend `.env`) | `http://localhost:8000` |

Derived values (computed automatically):
- `AISUITE_MODEL` = `{PROVIDER}:{MODEL_NAME}`
- `DATA_DIR` = `{project_root}/Backend/data/`
- `CHROMA_PERSIST_DIR` = `{DATA_DIR}/chroma/`

## 3. Provider-Specific Setup

### Ollama (Local)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull qwen2.5:7b`
3. Ollama runs on `http://localhost:11434` by default

```env
PROVIDER=ollama
MODEL_NAME=qwen2.5:7b
API_KEY=
```

### OpenAI

```env
PROVIDER=openai
MODEL_NAME=gpt-4o-mini
API_KEY=sk-...
```

### Anthropic

```env
PROVIDER=anthropic
MODEL_NAME=claude-3-5-sonnet-20241022
API_KEY=sk-ant-...
```

### DeepSeek

```env
PROVIDER=deepseek
MODEL_NAME=deepseek-chat
API_KEY=sk-...
```

### Google Gemini

```env
PROVIDER=gemini
MODEL_NAME=gemini-pro
API_KEY=AIza...
```

### Grok (xAI)

```env
PROVIDER=grok
MODEL_NAME=grok-beta
API_KEY=xai-...
```

## 4. Run the Application

From the project root:

**Start both backend and frontend:**
```bash
npm run fboth
```

**Or start them separately:**

```bash
# Terminal 1 - Backend (FastAPI on port 8000)
npm run backend

# Terminal 2 - Frontend (Vite dev server on port 5173)
npm run frontend
```

The frontend is accessible at `http://localhost:5173`. API requests are proxied to the backend at `http://localhost:8000`.

## 5. Frontend Dependencies

The `postinstall` script in `package.json` automatically runs `npm install` in the `frontend/` directory when you run `npm install` at the root. If you need to install frontend deps manually:

```bash
cd frontend
npm install
```

## Data Directory

All runtime data is stored in `Backend/data/`:

```
Backend/data/
├── chatbot.db          # SQLite database
├── chroma/             # ChromaDB vector collections
├── images/             # Avatar images (personas + chronicles)
└── files/              # Uploaded PDF files
```

## Troubleshooting

### Circular Reference Error
If you see a "Circular reference detected" error, ensure the `messages` list passed to `get_response()` is a flat list of message dictionaries with no nested objects.

### Session Growing Too Large
The app uses summarization and trimming to manage conversation history. If sessions grow unexpectedly large, increase trimming frequency in `memory.py` or shorten saved history.

### Ollama Connection Refused
Ensure Ollama is running: `ollama serve`. Verify with `curl http://localhost:11434`.

### ChromaDB Permission Errors
Ensure the `Backend/data/chroma/` directory is writable by the application process.
