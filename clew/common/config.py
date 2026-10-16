"""Config loading: YAML files in config/ plus environment variables (CLAUDE.md rule 8)."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("CLEW_CONFIG_DIR", ROOT / "config"))


@cache
def load(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml as a dict."""
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f) or {}


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def shop_url() -> str:
    return env("SHOP_URL", "http://localhost:8090").rstrip("/")


def graph_name() -> str:
    return env("CLEW_GRAPH", "nebula_live")


def lease_ms(kind: str) -> int:
    return int(load("session")["leases_ms"][kind])


def llm_backend() -> str:
    """vertex | gemini_api | off. `off` selects the deterministic page reader and reporter."""
    return env("LLM_BACKEND", "off").strip().lower()
