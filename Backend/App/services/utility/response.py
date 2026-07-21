import time
from langchain_openai import ChatOpenAI
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .config import AISUITE_MODEL, PROVIDER, API_KEY

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
            "type": {"type": "string", "enum": ["character", "location", "faction", "item", "concept"]},
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


def _get_schema(mode, type=None):
    if mode == "chronicle_beats":
        return BEAT_SCHEMA
    if mode == "chronicle_entities":
        return ENTITIES_SCHEMA
    if mode == "characters":
        schemas = {
            "personality": CHARACTER_PERSONALITY_SCHEMA,
            "backstory": CHARACTER_BACKSTORY_SCHEMA,
            "fighting_style": CHARACTER_FIGHTING_STYLE_SCHEMA,
        }
        return schemas.get(type, CHARACTER_FIGHTING_STYLE_SCHEMA)
    return None 


def _stub_client():
    class _StubResponse:
        def __init__(self, content):
            self.content = content

    class _StubClient:
        def invoke(self, prompt):
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


def _build_deepseek(model_name, schema):
    kwargs = {
        "model": model_name,
        "api_key": API_KEY,
        "base_url": "https://api.deepseek.com",
        "temperature": 0,
    }
    if schema is not None:
        kwargs["format"] = schema
    return ChatOpenAI(**kwargs)


def _build_ollama(model_name, schema):
    from langchain_ollama import ChatOllama

    if model_name and ":" in model_name:
        model_name = model_name.split(":", 1)[1]

    kwargs = {
        "model": model_name,
        "base_url": "http://localhost:11434",
        "temperature": 0,
    }
    if schema is not None:
        kwargs["num_ctx"] = 8192
        kwargs["format"] = schema
    return ChatOllama(**kwargs)


def _build_anthropic(model_name, schema):
    from langchain_anthropic import ChatAnthropic

    kwargs = {
        "model": model_name,
        "api_key": API_KEY,
        "temperature": 0,
    }
    if schema is not None:
        kwargs["format"] = schema  # confirm langchain_anthropic supports this kwarg before relying on it
    return ChatAnthropic(**kwargs)


def _build_openai(model_name, schema):
    kwargs = {
        "model": model_name,
        "api_key": API_KEY,
        "temperature": 0,
    }
    if schema is not None:
        kwargs["format"] = schema
    return ChatOpenAI(**kwargs)

def _build_gemini(model_name, schema):
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs = {
        "model": model_name,
        "google_api_key": API_KEY,
        "temperature": 0,
    }
    if schema is not None:
        kwargs["response_schema"] = schema  # ChatGoogleGenerativeAI uses response_schema, not format
        kwargs["response_mime_type"] = "application/json"
    return ChatGoogleGenerativeAI(**kwargs)


def _build_grok(model_name, schema):
    kwargs = {
        "model": model_name,
        "api_key": API_KEY,
        "base_url": "https://api.x.ai/v1",
        "temperature": 0,
    }
    if schema is not None:
        kwargs["format"] = schema
    return ChatOpenAI(**kwargs)


PROVIDER_BUILDERS = {
    "deepseek": _build_deepseek,
    "ollama": _build_ollama,
    "anthropic": _build_anthropic,
    "openai": _build_openai,
    "gemini": _build_gemini,
    "grok": _build_grok,
}


def get_client(mode, type=None):
    schema = _get_schema(mode, type)
    builder = PROVIDER_BUILDERS.get(PROVIDER)

    if builder is not None:
        try:
            return builder(AISUITE_MODEL, schema)
        except Exception as e:
            print(f"[Warning] {PROVIDER} client init failed: {e}")
            # fall through to stub

    return _stub_client()



def get_response(prompt, mode, type=None, retries=3, backoff=2, response_timeout=15):

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
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(client.invoke, prompt)
                try:
                    response = future.result(timeout=response_timeout)
                except FutureTimeoutError:
                    raise TimeoutError(
                        f"No response after {response_timeout}s cooldown"
                    )

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