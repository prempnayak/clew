"""Times and IDs. Times are epoch milliseconds; sequential IDs come from graph counters (Q41)."""

from __future__ import annotations

import time
import uuid


def now_ms() -> int:
    return int(time.time() * 1000)


def short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"
