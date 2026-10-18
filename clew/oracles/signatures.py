"""Bug signatures, one format per kind. Same signature = same bug (MERGE in Q12)."""

from __future__ import annotations

import re

_HEX = re.compile(r"\b[0-9a-f]{8,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def normalize_message(message: str) -> str:
    """Lower-case; quoted values, hex/uuid ids and digits → '#'; whitespace collapsed."""
    m = message.strip().splitlines()[0] if message.strip() else ""
    m = m.lower()
    m = _QUOTED.sub("'#'", m)
    m = _HEX.sub("#", m)
    m = re.sub(r"\d+", "#", m)
    return re.sub(r"\s+", " ", m).strip()


def http_5xx(method: str, route: str, status: int) -> str:
    return f"http_5xx|{method.upper()} {route}|{status}"


def pageerror(route: str, message: str) -> str:
    return f"pageerror|{route}|{normalize_message(message)}"


def console_error(route: str, message: str) -> str:
    return f"console_error|{route}|{normalize_message(message)}"


def rule(rule_id: str, state_key: str) -> str:
    """`rule|<rule id>|<route>|<hash8>`: the state key without its auth part, so the same broken page seen
    logged in and logged out is one bug."""
    route, _auth, h = state_key.rsplit("|", 2)
    return f"rule|{rule_id}|{route}|{h}"


def nav_timeout(state_key: str, action_key: str) -> str:
    return f"nav_timeout|{state_key}|{action_key}"


def regression(action_key: str) -> str:
    """`regression|<route>|<hash8>#<role:target>`: the action key without its auth part, and for forms without
    the input case, so the same broken button (logged in or out) or form (valid, invalid or empty input) is one
    regression; every affected action becomes one of its triggers."""
    state, _, rest = action_key.partition("#")
    route, _auth, h = state.rsplit("|", 2)
    if rest.startswith("form:"):
        rest = rest.rsplit(":", 1)[0]
    return f"regression|{route}|{h}#{rest}"
