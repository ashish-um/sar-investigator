"""
LLM factory for the AML Investigation Agent.

Reads LLM_PROVIDER from .env ("groq", "gemini", or "deepseek"), validates the
corresponding API key, and returns the appropriate LangChain chat model.
All providers share the BaseChatModel interface, so nothing downstream
needs to know which provider is active.

Groq supports key hopping: set GROQ_API_KEYS to a comma-separated list
of API keys. On a 429 rate limit error, the wrapper automatically rotates
to the next key and retries the request.
"""

import os
import logging
from typing import Any, Iterator, List, Optional
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.5-flash",
    "deepseek": "deepseek/deepseek-chat",
}


# ── Groq Key Pool ────────────────────────────────────────────────────────

class _GroqKeyPool:
    """Round-robin pool of Groq API keys."""

    def __init__(self, keys: List[str]):
        if not keys:
            raise ValueError("No Groq API keys provided")
        self.keys = keys
        self._index = 0

    @property
    def current(self) -> str:
        return self.keys[self._index]

    def rotate(self) -> str:
        """Move to the next key and return it."""
        self._index = (self._index + 1) % len(self.keys)
        logger.info(f"Rotated to Groq key index {self._index}")
        return self.current

    def __len__(self) -> int:
        return len(self.keys)


def _build_groq_pool() -> _GroqKeyPool:
    """Build key pool from GROQ_API_KEYS (comma-separated) or GROQ_API_KEY."""
    multi = os.getenv("GROQ_API_KEYS", "").strip()
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
    else:
        single = os.getenv("GROQ_API_KEY", "").strip()
        keys = [k.strip() for k in single.split(",") if k.strip()] if single else []

    if not keys:
        raise ValueError(
            "No Groq API keys found. Set GROQ_API_KEYS (comma-separated) "
            "or GROQ_API_KEY in .env"
        )
    return _GroqKeyPool(keys)


# ── Key-Hopping Wrapper ──────────────────────────────────────────────────

def _make_groq_with_hopping(model: str, pool: _GroqKeyPool):
    """
    Return a ChatGroq instance wrapped with key-hopping retry logic.

    On a 429 RateLimitError, it rotates to the next key in the pool,
    rebuilds the ChatGroq client, and retries. Each key is tried once
    before giving up.
    """
    from langchain_groq import ChatGroq
    import groq as groq_sdk

    class _KeyHoppingGroq(ChatGroq):
        """ChatGroq subclass that auto-rotates API keys on rate limit."""

        _key_pool: _GroqKeyPool  # type: ignore

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, key_pool: _GroqKeyPool, **kwargs: Any):
            super().__init__(**kwargs)
            # Store pool on the instance using object.__setattr__
            # to bypass Pydantic's frozen model restrictions
            object.__setattr__(self, '_key_pool', key_pool)

        def _rebuild_client(self) -> None:
            """Swap the internal Groq client to use the pool's current key."""
            self.api_key = self._key_pool.current
            # Force LangChain to rebuild the underlying httpx client
            self.client = None  # type: ignore
            self.async_client = None  # type: ignore
            # Re-validate to rebuild clients
            self.validate_environment()  # type: ignore

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            **kwargs: Any,
        ) -> ChatResult:
            attempts = len(self._key_pool)
            last_error = None
            for attempt in range(attempts):
                try:
                    return super()._generate(messages, stop=stop, **kwargs)
                except groq_sdk.RateLimitError as e:
                    last_error = e
                    if attempt < attempts - 1:
                        next_key = self._key_pool.rotate()
                        logger.warning(
                            f"Rate limit hit on key index "
                            f"{(self._key_pool._index - 1) % len(self._key_pool)}. "
                            f"Hopping to key ...{next_key[-6:]}"
                        )
                        self._rebuild_client()
                    else:
                        logger.error("All Groq API keys exhausted (rate limited)")
            raise last_error  # type: ignore

        def _stream(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            **kwargs: Any,
        ) -> Iterator[ChatGenerationChunk]:
            attempts = len(self._key_pool)
            last_error = None
            for attempt in range(attempts):
                try:
                    yield from super()._stream(messages, stop=stop, **kwargs)
                    return  # success — exit the retry loop
                except groq_sdk.RateLimitError as e:
                    last_error = e
                    if attempt < attempts - 1:
                        next_key = self._key_pool.rotate()
                        logger.warning(
                            f"Rate limit hit on key index "
                            f"{(self._key_pool._index - 1) % len(self._key_pool)}. "
                            f"Hopping to key ...{next_key[-6:]}"
                        )
                        self._rebuild_client()
                    else:
                        logger.error("All Groq API keys exhausted (rate limited)")
            raise last_error  # type: ignore

    llm = _KeyHoppingGroq(
        key_pool=pool,
        model=model,
        temperature=0,
        api_key=pool.current,
    )
    logger.info(
        f"Groq initialised with {len(pool)} key(s), "
        f"starting on key ...{pool.current[-6:]}"
    )
    return llm


# ── Public Factory ────────────────────────────────────────────────────────

def get_llm():
    """Return a LangChain chat model based on LLM_PROVIDER in .env."""

    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    model = os.getenv("LLM_MODEL", "").strip() or _DEFAULTS.get(provider)

    if provider == "groq":
        pool = _build_groq_pool()
        return _make_groq_with_hopping(model, pool)

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            google_api_key=api_key,
        )

    elif provider == "deepseek":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in .env")

        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=0,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'groq', 'gemini', 'deepseek'"
        )
