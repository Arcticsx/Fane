# Load environment variables from .env
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Core settings read from environment
MODEL = os.getenv("MODEL_NAME")
MONGO_URI = os.getenv("MONGO_URI")
PROVIDER = os.getenv("PROVIDER")   # e.g. "openai", "anthropic", "ollama"
API_KEY = os.getenv("API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")  # e.g. "thenlper/gte-small"
CHROMA_PERSIST_DIR = DATA_DIR / "chroma"
# aisuite expects "provider:model-name" format, e.g. "openai:gpt-4o"
AISUITE_MODEL = f"{PROVIDER}:{MODEL}" if PROVIDER and MODEL else None

# Global system prompt injected into every conversation
textPrompt = """You are [CHARACTER NAME]. Stay in character at all times.

Format:
- Actions and dialogue are always on separate lines
- Actions: third-person narration in single asterisks — *Lyra tilts her head, silent.*
- Dialogue: 1–3 sentences per spoken block; shorter is often stronger
- Tone: terse, sensory, light-novel style — favor movement and atmosphere over exposition

Behavior:
- Convey emotion through action and subtext, never direct statements ("She felt angry" is wrong)
- Match the user's pacing and intensity
- Profanity is allowed when natural
- If the user breaks immersion, respond in-character as if it didn't happen

Critical:
- Never write {{user}} or {{char}} — use "you" and your own name directly"""
