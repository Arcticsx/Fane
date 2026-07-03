# Handles all LLM API calls via LangChain, with retry logic

import time
from langchain_openai import ChatOpenAI

try:
    from .config import AISUITE_MODEL, PROVIDER, API_KEY
except ImportError:
    from config import AISUITE_MODEL, PROVIDER, API_KEY


def get_client():
    if PROVIDER == "deepseek":
        return ChatOpenAI(
            model=AISUITE_MODEL,
            api_key=API_KEY,
            base_url="https://api.deepseek.com",
            temperature=0
        )

    elif PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=AISUITE_MODEL,
            base_url="http://localhost:11434"
        )

    raise ValueError(f"Unsupported provider: {PROVIDER}")


def get_response(messages, retries=3, backoff=2):
    client = get_client()
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
            response = client.invoke(messages)

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