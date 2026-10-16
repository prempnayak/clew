"""One-line structured logs to stdout."""

from __future__ import annotations

import json
import logging
import sys


def get(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def kv(**fields: object) -> str:
    return json.dumps(fields, default=str, separators=(",", ":"))
