"""Run the optional Groq assistant and provide a local fallback.

Model names and generation settings live in ``config.py``. Every live result
records the model that actually answered, while a missing key or failed request
returns a deterministic summary built from the scored data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import (
    DEFAULT_GROQ_MODEL,
    GROQ_FALLBACK_MODELS,
    GROQ_MAX_TOKENS,
    GROQ_TEMPERATURE,
)

from pathlib import Path


@dataclass
class LLMResult:
    """Standardized output container for AI generation responses."""
    text: str
    live: bool
    warning: str | None = None
    model: str | None = None  # the actual Groq model id that answered, when live


def get_groq_api_key() -> str:
    """
    Retrieve Groq API key from (in priority order):
    1. OS environment variable (GROQ_API_KEY)
    2. Streamlit secrets (st.secrets['GROQ_API_KEY'])
    3. Project root .env file
    """
    # 1. Environment variable
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key

    # 2. Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            k = str(st.secrets["GROQ_API_KEY"]).strip()
            if k:
                return k
    except Exception:
        pass

    # 3. .env file
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if k:
                        return k
        except Exception:
            pass

    return ""


def execute_groq_chat(messages: list[dict[str, str]]) -> LLMResult:
    """
    Execute a chat completion request against the configured Groq API.
    
    If GROQ_API_KEY is not set or the request encounters a network/rate-limit issue,
    returns an LLMResult with live=False and an informative advisory message.
    """
    api_key = get_groq_api_key()
    if not api_key:
        return LLMResult(
            text="",
            live=False,
            warning="Groq API key not detected. Showing the local evidence summary. Set GROQ_API_KEY to enable the live assistant."
        )

    from groq import Groq
    client = Groq(api_key=api_key)

    models_to_try = [DEFAULT_GROQ_MODEL] + [m for m in GROQ_FALLBACK_MODELS if m != DEFAULT_GROQ_MODEL]
    last_err = ""

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=GROQ_TEMPERATURE,
                max_tokens=GROQ_MAX_TOKENS,
            )
            text = response.choices[0].message.content.strip()
            return LLMResult(text=text, live=True, model=model_name)
        except Exception as exc:
            err_msg = str(exc)
            last_err = err_msg
            # If model does not exist or account lacks access, fall back to next model candidate
            if "does not exist" in err_msg.lower() or "404" in err_msg or "access" in err_msg.lower():
                continue
            break

    if "rate_limit" in last_err.lower():
        friendly_err = "Groq rate limit reached. Showing the local evidence summary instead."
    elif "invalid_api_key" in last_err.lower() or "authentication" in last_err.lower():
        friendly_err = "Invalid Groq API key. Check your key at console.groq.com."
    else:
        friendly_err = f"Groq API connection issue ({last_err[:120]}). Reverting to local grounded analysis."

    return LLMResult(text="", live=False, warning=friendly_err)
