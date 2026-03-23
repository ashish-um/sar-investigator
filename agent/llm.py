"""
LLM factory for the AML Investigation Agent.

Reads LLM_PROVIDER from .env ("groq" or "gemini"), validates the
corresponding API key, and returns the appropriate LangChain chat model.
Both ChatGroq and ChatGoogleGenerativeAI share the BaseChatModel interface,
so nothing downstream needs to know which provider is active.
"""

import os
from dotenv import load_dotenv

load_dotenv()

_DEFAULTS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.5-flash",
}


def get_llm():
    """Return a LangChain chat model based on LLM_PROVIDER in .env."""

    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    model = os.getenv("LLM_MODEL", "").strip() or _DEFAULTS.get(provider)

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in .env")

        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=0,
            api_key=api_key,
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

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'groq', 'gemini'"
        )
