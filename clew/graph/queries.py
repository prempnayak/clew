"""Query loader. Cypher lives only in queries/QNN_name.cypher (CLAUDE.md rule 2).

Each file starts with a header comment:
    // QNN name
    // Purpose: ...
    // Params: ...
    // Callers: ...
Code loads queries by ID ("Q03b") and always passes values as $parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

QUERY_DIR = Path(__file__).parent / "queries"
_FILE = re.compile(r"^(Q\d+[a-z]?)_(\w+)\.cypher$")


@dataclass(frozen=True)
class Query:
    id: str
    name: str
    purpose: str
    params: str
    callers: str
    text: str

    @property
    def statements(self) -> list[str]:
        """Q01 holds several statements separated by ';'. Every other query is one statement."""
        return [s.strip() for s in self.text.split(";") if s.strip()]


def _parse(path: Path) -> Query:
    m = _FILE.match(path.name)
    if not m:
        raise ValueError(f"bad query file name: {path.name}")
    header: dict[str, list[str]] = {"purpose": [], "params": [], "callers": []}
    body: list[str] = []
    field = None
    for line in path.read_text().splitlines():
        if line.startswith("//"):
            content = line[2:].strip()
            low = content.lower()
            for key in header:
                if low.startswith(key + ":"):
                    field = key
                    content = content[len(key) + 1 :].strip()
                    break
            else:
                if field is None:  # the "// QNN name" title line
                    continue
            header[field].append(content)
        else:
            body.append(line)
    return Query(
        id=m.group(1),
        name=m.group(2),
        purpose=" ".join(header["purpose"]),
        params=" ".join(header["params"]),
        callers=" ".join(header["callers"]),
        text="\n".join(body).strip(),
    )


@lru_cache(maxsize=1)
def all_queries() -> dict[str, Query]:
    out = {}
    for path in sorted(QUERY_DIR.glob("Q*.cypher")):
        q = _parse(path)
        out[q.id] = q
    return out


def get(qid: str) -> Query:
    try:
        return all_queries()[qid]
    except KeyError:
        raise KeyError(f"unknown query id {qid}") from None
