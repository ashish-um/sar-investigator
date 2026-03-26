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
    "cerebras": "qwen-3-235b-a22b-instruct-2507",
    "mistral": "mistral-large-latest",
    "nvidia": "deepseek-ai/deepseek-v3.1",
}


# ── Key Pool ─────────────────────────────────────────────────────────────

_groq_keys: List[str] = []
_current_groq_index = 0

def _init_groq_keys():
    """Load keys from environment variables."""
    global _groq_keys
    if _groq_keys:
        return
        
    multi = os.getenv("GROQ_API_KEYS", "").strip()
    if multi:
        _groq_keys = [k.strip() for k in multi.split(",") if k.strip()]
    else:
        single = os.getenv("GROQ_API_KEY", "").strip()
        _groq_keys = [k.strip() for k in single.split(",") if k.strip()] if single else []

    if not _groq_keys:
        raise ValueError(
            "No Groq API keys found. Set GROQ_API_KEYS (comma-separated) "
            "or GROQ_API_KEY in .env"
        )
    logger.info(f"Loaded {len(_groq_keys)} Groq API key(s).")

def get_current_groq_key() -> str:
    _init_groq_keys()
    return _groq_keys[_current_groq_index]

def rotate_groq_key() -> str:
    """Move to the next Groq key in the pool and return it."""
    global _current_groq_index
    _init_groq_keys()
    _current_groq_index = (_current_groq_index + 1) % len(_groq_keys)
    logger.warning(
        f"Rotated Groq API key. New index: {_current_groq_index}"
    )
    return _groq_keys[_current_groq_index]

def get_groq_key_count() -> int:
    _init_groq_keys()
    return len(_groq_keys)


# ── Public Factory ────────────────────────────────────────────────────────

def get_llm_config() -> dict:
    """Return the active LLM provider and model configuration."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    model = os.getenv("LLM_MODEL", "").strip() or _DEFAULTS.get(provider)
    return {"provider": provider, "model": model}

def get_llm():
    """Return a LangChain chat model based on LLM_PROVIDER in .env."""

    config = get_llm_config()
    provider = config["provider"]
    model = config["model"]

    if provider == "groq":
        from langchain_groq import ChatGroq
        
        # When rate limit hits, graph.py will call rotate_groq_key()
        # and re-invoke get_llm() which will grab the new key.
        return ChatGroq(
            model=model,
            temperature=0,
            api_key=get_current_groq_key(),
        )

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

    elif provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set.")
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=model,
            api_key=api_key,
            temperature=0,
        )

    elif provider == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY environment variable is not set.")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0,
        )

    elif provider == "llamacpp":
        from langchain_openai import ChatOpenAI
        host = os.getenv("LLAMACPP_HOST", "http://localhost:8080")
        # llama.cpp doesn't need a real key but LangChain requires a non-empty string
        return ChatOpenAI(
            model="local",                        # ignored by llama.cpp, just a label
            api_key="not-required",
            base_url=f"{host}/v1",
            temperature=0,
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

    elif provider == "cerebras":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY not set. Add it to your .env file.")
        return ChatOpenAI(
            model=model or "qwen-3-235b-a22b-instruct-2507",
            base_url="https://api.cerebras.ai/v1",
            api_key=api_key,
            temperature=0,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'groq', 'gemini', 'deepseek', 'cerebras'"
        )
