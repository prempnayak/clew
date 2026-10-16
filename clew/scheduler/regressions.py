"""The regression pipeline (handoff §12.8), run by the watcher once a release's replay jobs have drained.

For every action whose outcome changed (Q19): the affected pages (Q35, before marking), a `regression` bug
(Q12, status new, so the Reporter queues its confirmation), and the action marked broken (Q20) so routes avoid it.
Idempotent: an action that already has its regression bug is skipped.
"""

from __future__ import annotations

import json

from clew.common.ids import now_ms
from clew.common.log import get, kv
from clew.graph.client import Graph
from clew.oracles import signatures

log = get("regressions")


def process(graph: Graph, previous: str, release: str) -> list[str]:
    filed = []
    for row in graph.run("Q19", {"previous": previous, "release": release}):
        sig = signatures.regression(row["action"])
        known = graph.one("Q38", {"sig": sig}, read_only=True)
        if known and row["action"] in known["triggers"]:
            continue  # already processed
        affected = sorted({r["page"] for r in graph.run("Q35", {"action": row["action"]}, read_only=True)})
        evidence = {
            "message": row["error"] or f"now leads to {row['now_target']}",
            "label": row["label"],
            "page": row["page"],
            "was_target": row["was_target"],
            "was_target_key": row["was_target_key"],
            "now_target": row["now_target"],
            "now_target_key": row["now_target_key"],
            "previous": previous,
            "release": release,
            "affected_pages": affected,
            "agent": "release-watcher",
        }
        title = f"'{row['label']}' on {row['page']} no longer reaches {row['was_target']} ({release})"
        graph.run(
            "Q12",
            {
                "action": row["action"],
                "release": release,
                "sig": sig,
                "kind": "regression",
                "title": title,
                "initial_status": "new",
                "severity": "P2",
                "evidence": json.dumps(evidence),
                "now": now_ms(),
            },
        )
        graph.run("Q20", {"action": row["action"]})
        graph.publish("bug.updated", sig=sig, status=known["status"] if known else "new")
        log.info(kv(regression=row["action"], was=row["was_target"], now=row["now_target"], affected=affected))
        if not known:
            filed.append(sig)
    return filed
