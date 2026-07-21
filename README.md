# Fane -- Local AI Conversational App

A full-stack application for immersive roleplay conversations and chronicle storytelling with AI-powered characters. Supports multiple LLM providers, persistent sessions, customizable personalities, and a document-processing pipeline that turns PDFs into RAG-powered narrative experiences.

## Languages & Tools

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![REACT](https://img.shields.io/badge/-ReactJs-61DAFB?style=for-the-badge&logo=react&logoColor=white)
![JAVASCRIPT](https://shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=JavaScript&logoColor=000)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
[![Ollama](https://img.shields.io/badge/Ollama-fff?style=for-the-badge&logo=ollama&logoColor=000)](#)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)

## Features

- **Multiple AI Providers** -- OpenAI, Anthropic Claude, DeepSeek, Google Gemini, Grok, and local Ollama models
- **Persona Chat** -- Create custom character personalities with system prompts, scenarios, and avatars
- **Persistent Sessions** -- Conversations are saved locally and can be resumed later
- **Memory Management** -- Automatic conversation summarization and trimming
- **Chronicle System** -- Upload PDFs (novels, game books) and build a structured knowledge base
- **RAG-Powered Chat** -- Chronicle chat uses vector search over extracted PDF content for narrative context
- **Story Beat Extraction** -- Automatic extraction of plot points, character arcs, and world events
- **Entity Processing** -- Characters and lore entities are extracted, classified, and analyzed per chapter
- **Theming** -- 8 built-in themes + custom theme creation with background image support

## Quick Start

```bash
# 1. Set up virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure environment
echo "PROVIDER=ollama\nMODEL_NAME=qwen2.5:7b\nEMBEDDING_MODEL=thenlper/gte-small" > .env

# 3. Run
npm run fboth
```

Open `http://localhost:5173` in your browser.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, data flows, component overview |
| [Setup & Installation](docs/setup.md) | Prerequisites, configuration, provider setup |
| [API Reference](docs/api-reference.md) | All REST endpoints with request/response schemas |
| [RAG Pipeline](docs/rag-pipeline.md) | Document processing, beat extraction, entity processing |
| [Database Schema](docs/database-schema.md) | SQLAlchemy models, relationships, ER diagram |
| [Frontend Guide](docs/frontend-guide.md) | React components, routing, theming system |

## Project Structure

```
Backend/
├── App/
│   ├── api/           # FastAPI routers (chat, chronicle, documents)
│   ├── models/        # SQLAlchemy models (chat + chronicle domains)
│   └── services/      # Business logic (chat, documents, beats, entities, utility)
├── data/              # SQLite DB, ChromaDB, uploaded files
└── tests/             # pytest test suite

frontend/
├── src/
│   ├── components/    # 14 React components
│   ├── api.js         # API client
│   ├── App.jsx        # Root component with routing
│   └── themes.js      # Theme definitions
└── package.json
```

## Dependencies

**Python:** FastAPI, SQLAlchemy, ChromaDB, LangChain (OpenAI/Anthropic/Ollama/Gemini), PyMuPDF, SentenceTransformers

**Frontend:** React 18, React Router 7, Vite 6, Tailwind CSS 4, Lucide React

## Testing

```bash
cd Backend
pytest
```

## License

See [license](license) file for details.
