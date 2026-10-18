"""Structured-output calls to the configured model.

LLM_BACKEND chooses the provider and config/models.yaml the model per use:
- vertex / gemini_api: google-genai with `response_schema` and `thinking_level`;
- openai: any OpenAI-compatible server (LM Studio during development) with a JSON-schema response format;
- off: no client is ever created; callers use their deterministic fallbacks.
Temperature is left at the provider default. 429 and 5xx responses are retried with backoff.
"""

from __future__ import annotations

import re
import time
from functools import lru_cache

import httpx
from pydantic import BaseModel

from clew.common.config import env, llm_backend, load
from clew.common.log import get

log = get("llm")


class LLMUnavailable(RuntimeError):
    pass


def profile() -> str:
    b = llm_backend()
    return "openai" if b == "openai" else "gemini"


def model_cfg(use: str) -> dict:
    return load("models")[profile()][use]


def enabled(use: str) -> bool:
    """Is a model switched on for this use? (LLM_BACKEND=off disables every use.)"""
    if llm_backend() == "off":
        return False
    cfg = load("models")
    return use in cfg.get(profile(), {}) and use not in cfg.get("disabled", [])


def model_name(use: str) -> str:
    return model_cfg(use)["model"] if enabled(use) else "deterministic"


@lru_cache(maxsize=1)
def genai_client():
    from google import genai

    backend = llm_backend()
    if backend == "vertex":
        return genai.Client(
            vertexai=True, project=env("GOOGLE_CLOUD_PROJECT"), location=env("GOOGLE_CLOUD_LOCATION", "global")
        )
    if backend == "gemini_api":
        return genai.Client(api_key=env("GOOGLE_API_KEY"))
    raise LLMUnavailable(f"LLM_BACKEND={backend}")


def _strip(text: str) -> str:
    """Drop reasoning blocks and code fences some local models add around JSON."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    return m.group(1) if m else text


def _retryable(status: int) -> bool:
    return status == 429 or status >= 500


def _openai(use: str, system: str, prompt: str, schema: type[BaseModel]) -> str:
    base = env("OPENAI_BASE_URL", "http://localhost:1234/v1").rstrip("/")
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {env('OPENAI_API_KEY', 'local')}"},
        timeout=float(env("LLM_TIMEOUT_S", "120")),
        json={
            "model": model_cfg(use)["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": True},
            },
        },
    )
    if r.status_code >= 400:
        raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:200]}", request=r.request, response=r)
    return _strip(r.json()["choices"][0]["message"]["content"] or "")


def _gemini(use: str, system: str, prompt: str, schema: type[BaseModel]) -> str:
    from google.genai import types

    cfg = model_cfg(use)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=cfg.get("thinking_level", "low").upper()),
    )
    return genai_client().models.generate_content(model=cfg["model"], contents=prompt, config=config).text


def generate[T: BaseModel](use: str, system: str, prompt: str, schema: type[T], retries: int = 4) -> T:
    """One structured call for `use` (a key of config/models.yaml), validated with the pydantic schema."""
    if not enabled(use):
        raise LLMUnavailable(f"{use} is not enabled")
    call = _openai if profile() == "openai" else _gemini
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            return schema.model_validate_json(call(use, system, prompt, schema))
        except httpx.HTTPStatusError as e:
            if attempt < retries and _retryable(e.response.status_code):
                pass
            else:
                raise
        except Exception as e:  # noqa: BLE001 - google-genai APIError carries .code
            code = getattr(e, "code", None)
            if not (isinstance(code, int) and _retryable(code) and attempt < retries):
                raise
        log.warning("retrying %s (%.1fs)", use, delay)
        time.sleep(delay)
        delay *= 2
    raise LLMUnavailable("unreachable")


def adk_model(use: str):
    """The model object for an ADK LlmAgent: a Gemini model id, or LiteLLM for an OpenAI-compatible server."""
    cfg = model_cfg(use)
    if profile() == "openai":
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(
            model=f"openai/{cfg['model']}",
            api_base=env("OPENAI_BASE_URL", "http://localhost:1234/v1"),
            api_key=env("OPENAI_API_KEY", "local"),
        )
    return cfg["model"]


def adk_config(use: str):
    """GenerateContentConfig for an ADK agent (thinking level only for Gemini)."""
    from google.genai import types

    if profile() == "openai":
        return None
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level=model_cfg(use).get("thinking_level", "low").upper())
    )
