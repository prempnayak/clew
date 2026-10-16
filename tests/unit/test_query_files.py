"""Every query file has a complete header and only $parameters (CLAUDE.md rule 2)."""

import re

from clew.graph.queries import all_queries

HANDOFF_IDS = """Q01 Q02 Q03 Q03b Q04 Q05 Q06 Q06b Q07 Q08 Q09 Q10 Q10b Q11 Q12 Q13 Q14 Q15 Q15b Q15c Q15d Q16 Q17
Q18 Q19 Q20 Q21 Q22 Q23 Q24 Q25 Q26 Q27 Q27b Q28 Q29 Q29b Q29c Q30 Q31 Q32 Q33 Q34a Q34b Q35 Q36 Q36b""".split()


def test_all_handoff_queries_exist():
    qs = all_queries()
    assert len(HANDOFF_IDS) == 47
    missing = [q for q in HANDOFF_IDS if q not in qs]
    assert not missing


def test_headers_complete():
    for q in all_queries().values():
        assert q.purpose, q.id
        assert q.params, q.id
        assert q.callers, q.id
        assert q.text, q.id


def test_no_string_formatting_markers():
    """Values arrive as $params, never through Python formatting."""
    for q in all_queries().values():
        assert not re.search(r"\{\w+\}", q.text), q.id
        assert "%s" not in q.text and "{}" not in q.text, q.id
