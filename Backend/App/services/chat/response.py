# Handles all LLM API calls via LangChain, with retry logic

import time
from langchain_openai import ChatOpenAI

try:
    from .config import AISUITE_MODEL, PROVIDER, API_KEY
except ImportError:
    from config import AISUITE_MODEL, PROVIDER, API_KEY

BEAT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "classification": {"type": "string", "enum": ["mandatory", "scene"]},
            "beat_type": {
                "type": "string",
                "enum": [
                    "decision_point", "transition", "dialogue", "combat",
                    "revelation", "exploration", "reaction", "flashback", "dream_vision",
                ],
            },
            "description": {"type": "string"},
            "start_page": {"type": "integer"},
            "end_page": {"type": "integer"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "requires": {"type": "array", "items": {"type": "string"}},
            "introduces": {"type": "array", "items": {"type": "string"}},
            "key_dialogues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["classification", "beat_type", "description", "start_page", "end_page"],
    },
}

ENTITIES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "enum": ["character", "location", "organization", "artifact", "concept"]},
            "pages": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["name", "type", "pages"],
    },
}


CHARACTER_PERSONALITY_SCHEMA = {
    "character_name": {"type": "string"},
    "has_sufficient_data": {"type": "boolean"},
    "summary": {"type": "string"},
    "traits": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "trait": {"type": "string"},
                "evidence_pages": {"type": "array", "items": {"type": "integer"}}
            }
        }
    },
    "contradictions": {"type": "array", "items": {"type": "string"}}  # per your system prompt's "note contradictions" rule
}

CHARACTER_BACKSTORY_SCHEMA = {
    "character_name": {"type": "string"},
    "has_sufficient_data": {"type": "boolean"},
    "new_revelations": {"type": "string"},  # only what's newly revealed in THIS segment
    "evidence_pages": {"type": "array", "items": {"type": "integer"}}
}

CHARACTER_FIGHTING_STYLE_SCHEMA = {
    "character_name": {"type": "string"},
    "has_combat_evidence": {"type": "boolean"},  # explicit, not inferred from empty list
    "summary": {"type": "string"},
    "traits": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "trait": {"type": "string"},
                "evidence_pages": {"type": "array", "items": {"type": "integer"}}
            }
        }
    }
}


def get_client(mode, type):
    
    if mode == "chat":
        if PROVIDER == "deepseek":
            try:
                return ChatOpenAI(
                    model=AISUITE_MODEL,
                    api_key=API_KEY,
                    base_url="https://api.deepseek.com",
                    temperature=0
                )
            except Exception as e:
                print(f"[Warning] deepseek client init failed: {e}")
                # fall through to stub

        elif PROVIDER == "ollama":
            try:
                from langchain_ollama import ChatOllama
                model_name = AISUITE_MODEL
                if model_name and ":" in model_name:
                    model_name = model_name.split(":", 1)[1]
                return ChatOllama(
                    model=model_name,
                    base_url="http://localhost:11434",
                    temperature=0,
                )
            except Exception as e:
                print(f"[Warning] ollama client init failed: {e}")
    elif mode == "chronicle_beats":
        if PROVIDER == "deepseek":
            try:
                return ChatOpenAI(
                    model=AISUITE_MODEL,
                    api_key=API_KEY,
                    base_url="https://api.deepseek.com",
                    temperature=0,
                    format=BEAT_SCHEMA,
                )
            except Exception as e:
                print(f"[Warning] deepseek client init failed: {e}")
                # fall through to stub

        elif PROVIDER == "ollama":
            try:
                from langchain_ollama import ChatOllama
                model_name = AISUITE_MODEL
                if model_name and ":" in model_name:
                    model_name = model_name.split(":", 1)[1]
                return ChatOllama(
                    model=model_name,
                    base_url="http://localhost:11434",
                    temperature=0,
                    num_ctx=8192,
                    format=BEAT_SCHEMA,
                )
            except Exception as e:
                print(f"[Warning] ollama client init failed: {e}")
    
    elif mode == "chronicle_entities":
        if PROVIDER == "deepseek":
            try:
                return ChatOpenAI(
                    model=AISUITE_MODEL,
                    api_key=API_KEY,
                    base_url="https://api.deepseek.com",
                    temperature=0,
                    format=ENTITIES_SCHEMA,
                )
            except Exception as e:
                print(f"[Warning] deepseek client init failed: {e}")
                # fall through to stub

        elif PROVIDER == "ollama":
            try:
                from langchain_ollama import ChatOllama
                model_name = AISUITE_MODEL
                if model_name and ":" in model_name:
                    model_name = model_name.split(":", 1)[1]
                return ChatOllama(
                    model=model_name,
                    base_url="http://localhost:11434",
                    temperature=0,
                    num_ctx=8192,
                    format=ENTITIES_SCHEMA,
                )
            except Exception as e:
                print(f"[Warning] ollama client init failed: {e}")
        
    elif mode == "characters":
        if PROVIDER == "deepseek":
            try:
                return ChatOpenAI(
                    model=AISUITE_MODEL,
                    api_key=API_KEY,
                    base_url="https://api.deepseek.com",
                    temperature=0,
                    format=CHARACTER_PERSONALITY_SCHEMA if type == "personality" else (CHARACTER_BACKSTORY_SCHEMA if type == "backstory" else CHARACTER_FIGHTING_STYLE_SCHEMA),
                )
            except Exception as e:
                print(f"[Warning] deepseek client init failed: {e}")
                # fall through to stub

        elif PROVIDER == "ollama":
            try:
                from langchain_ollama import ChatOllama
                model_name = AISUITE_MODEL
                if model_name and ":" in model_name:
                    model_name = model_name.split(":", 1)[1]
                return ChatOllama(
                    model=model_name,
                    base_url="http://localhost:11434",
                    temperature=0,
                    num_ctx=8192,
                    format=CHARACTER_PERSONALITY_SCHEMA if type == "personality" else (CHARACTER_BACKSTORY_SCHEMA if type == "backstory" else CHARACTER_FIGHTING_STYLE_SCHEMA),
                )
            except Exception as e:
                print(f"[Warning] ollama client init failed: {e}")
    
    

    # Fallback: when no provider is configured (local development/tests),
    # return a simple deterministic stub client so `/chat` remains usable.
    class _StubResponse:
        def __init__(self, content):
            self.content = content

    class _StubClient:
        def invoke(self, prompt):
            # If prompt is a list of messages, echo the last user message
            try:
                if isinstance(prompt, (list, tuple)) and prompt:
                    last = prompt[-1]
                    if isinstance(last, dict) and last.get("role") == "user":
                        return _StubResponse(f"Echo: {last.get('content')}")
                    if hasattr(last, "content"):
                        return _StubResponse(f"Echo: {str(last.content)}")
                return _StubResponse("Echo: Hello from local stub client.")
            except Exception:
                return _StubResponse("Echo: Hello from local stub client.")

    return _StubClient()


def get_response(prompt, mode, type, retries=3, backoff=2):
    client = get_client(mode, type)
    last_error = None

    TRANSIENT_KEYWORDS = (
        "rate limit", "429", "500",
        "502", "503", "connection"
    )

    TIMEOUT_KEYWORDS = (
        "timeout", "timed out"
    )

    for attempt in range(1, retries + 1):
        try:
            response = client.invoke(prompt)

            if not response.content:
                raise ValueError(
                    "Empty or malformed response from API"
                )

            return response.content

        except ValueError:
            raise

        except Exception as e:
            last_error = e
            err_str = str(e).lower()

            is_timeout = any(
                k in err_str for k in TIMEOUT_KEYWORDS
            )

            is_transient = any(
                k in err_str for k in TRANSIENT_KEYWORDS
            )

            if is_timeout or is_transient:
                wait = backoff * attempt * (3 if is_timeout else 1)

                print(
                    f"[Attempt {attempt}/{retries}] "
                    f"Retrying in {wait}s: {e}"
                )

                time.sleep(wait)

            else:
                raise

    raise RuntimeError(
        f"API call failed after {retries} attempts: {last_error}"
    )