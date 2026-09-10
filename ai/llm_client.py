"""
ai/llm_client.py — Free-Tier Groq LLM Client & Deterministic Fallback Engine
============================================================================
Integrates with Groq's high-speed inference engine using the open-weights
Llama-3.3-70B model.

Free Tier Information:
- Groq provides a 100% free tier (no credit card required)
- Allowance: 1,000 requests/day, 30 requests/minute on Llama-3.3-70B
- Get a free API key in 30 seconds at: https://console.groq.com

Zero-Dependency Local Fallback:
- If no GROQ_API_KEY is configured, or if offline, the system seamlessly falls
  back to deterministic, locally computed evidence explanations.
- The application is 100% functional without requiring any API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import (
    DEFAULT_GROQ_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_TEMPERATURE,
)


@dataclass
class LLMResult:
    """Standardized output container for AI generation responses."""
    text: str
    live: bool
    warning: str | None = None


def execute_groq_chat(messages: list[dict[str, str]]) -> LLMResult:
    """
    Execute a chat completion request against Groq's free-tier API.
    
    If GROQ_API_KEY is not set or the request encounters a network/rate-limit issue,
    returns an LLMResult with live=False and an informative advisory message.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return LLMResult(
            text="",
            live=False,
            warning="Groq API key not detected. Powered by free local deterministic engine. (To enable live Llama-3.3-70B, set GROQ_API_KEY from console.groq.com — it's completely free, no credit card required)."
        )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_GROQ_MODEL,
            messages=messages,
            temperature=GROQ_TEMPERATURE,
            max_tokens=GROQ_MAX_TOKENS,
        )
        text = response.choices[0].message.content.strip()
        return LLMResult(text=text, live=True)

    except Exception as exc:
        err_msg = str(exc)
        if "rate_limit" in err_msg.lower():
            friendly_err = "Groq free-tier rate limit reached. Reverting to local grounded analysis."
        elif "invalid_api_key" in err_msg.lower() or "authentication" in err_msg.lower():
            friendly_err = "Invalid Groq API key. Check your key at console.groq.com."
        else:
            friendly_err = f"Groq API connection issue ({err_msg[:120]}). Reverting to local grounded analysis."

        return LLMResult(text="", live=False, warning=friendly_err)
