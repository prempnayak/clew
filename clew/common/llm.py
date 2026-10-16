"""Structured-output calls to Gemini through google-genai (handoff §11.2, Appendix D).

Model IDs and thinking levels come from config/models.yaml. Temperature is left at the Gemini 3 default.
429 and 5xx responses are retried with backoff. LLM_BACKEND=off means no client is ever created.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from clew.common.config import env, llm_backend, load
from clew.common.log import get

T = TypeVar("T", bound=BaseModel)
log = get("llm")


class LLMUnavailable(RuntimeError):
    pass


def enabled(use: str) -> bool:
    """Is the model for this use switched on? (LLM_BACKEND=off disables every use.)"""
    if llm_backend() == "off":
        return False
    return bool(load("models").get(use, {}).get("enabled", True))


@lru_cache(maxsize=1)
def client():
    from google import genai

    backend = llm_backend()
    if backend == "vertex":
        return genai.Client(
            vertexai=True, project=env("GOOGLE_CLOUD_PROJECT"), location=env("GOOGLE_CLOUD_LOCATION", "global")
        )
    if backend == "gemini_api":
        return genai.Client(api_key=env("GOOGLE_API_KEY"))
    raise LLMUnavailable(f"LLM_BACKEND={backend}")


def generate[T: BaseModel](use: str, system: str, prompt: str, schema: type[T], retries: int = 4) -> T:
    """One structured call for `use` (a key of config/models.yaml), validated with the pydantic schema."""
    from google.genai import errors, types

    cfg = load("models")[use]
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=cfg.get("thinking_level", "low").upper()),
    )
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = client().models.generate_content(model=cfg["model"], contents=prompt, config=config)
            return schema.model_validate_json(resp.text)
        except errors.APIError as e:
            code = getattr(e, "code", 0) or 0
            if attempt < retries and (code == 429 or code >= 500):
                log.warning("retrying %s after %s (%.1fs)", use, code, delay)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise LLMUnavailable("unreachable")
