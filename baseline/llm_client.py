# STATUS: COMPLETE
"""OpenAI-compatible LLM client (Groq, Ollama, LM Studio, etc.)."""
from __future__ import annotations

import os

from openai import OpenAI


def _resolved_base_url() -> str:
    return (
        os.getenv("API_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.groq.com/openai/v1"
    ).strip().rstrip("/")


def get_openai_client() -> OpenAI:
    base_url = _resolved_base_url()
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    # Rubric / sample docs mention OPENAI_API_KEY; hackathon mandatoryreq names HF_TOKEN — accept both.
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("HF_TOKEN")
        or os.getenv("GROQ_API_KEY")
        or ""
    ).strip()
    lowered = base_url.lower()
    is_local = "localhost" in lowered or "127.0.0.1" in lowered
    if not api_key:
        if is_local:
            api_key = "ollama"
        else:
            raise ValueError(
                "Set OPENAI_API_KEY, HF_TOKEN (submission), or GROQ_API_KEY for cloud APIs, "
                "or API_BASE_URL / OPENAI_BASE_URL pointing at localhost (e.g. Ollama)."
            )

    return OpenAI(api_key=api_key, base_url=base_url)


def llm_endpoint_is_local() -> bool:
    base_url = _resolved_base_url().lower()
    return "localhost" in base_url or "127.0.0.1" in base_url
