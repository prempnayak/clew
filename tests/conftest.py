"""Shared fixtures: a throwaway graph `test_<uuid>` on embedded FalkorDB (falkordblite), deleted afterwards.

Set FALKORDB_HOST (and FALKORDB_EMBEDDED=0) to run the same tests against the pinned Docker image (V1).
"""

from __future__ import annotations

import os
import uuid

import pytest

from clew.graph.client import Graph, connect, embedded


def _db():
    if os.environ.get("FALKORDB_EMBEDDED", "1") == "1":
        return embedded()
    return connect()


@pytest.fixture(scope="session")
def db():
    return _db()


@pytest.fixture
def graph(db):
    g = Graph(db, f"test_{uuid.uuid4().hex[:8]}")
    g.schema()
    g.run("Q02", {"app": "nebula-gear", "base_url": "http://shop:8090", "release": "v1", "now": 1})
    yield g
    g.delete()
