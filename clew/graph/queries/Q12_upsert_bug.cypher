// Q12 upsert_bug
// Purpose: one node per signature (dedup); every sighting adds a trigger and a release.
//          A filed bug seen in a release for the first time gets needs_comment ("still present in v2").
// Params: $action, $release, $sig, $kind, $title, $initial_status, $severity, $evidence (JSON string), $now
// Callers: clew/explorer/worker.py, clew/scheduler/regressions.py
MATCH (a:Action {key: $action}), (rel:Release {name: $release})
MERGE (b:Bug {sig: $sig})
  ON CREATE SET b.kind = $kind, b.title = $title, b.status = $initial_status, b.first_seen = $now,
                b.count = 0, b.severity = $severity, b.release_found = $release, b.evidence = $evidence
WITH a, rel, b
OPTIONAL MATCH (b)-[seen:SEEN_IN]->(rel)
WITH a, rel, b, seen IS NULL AND b.status = 'filed' AS still_present
SET b.count = b.count + 1, b.last_seen = $now,
    b.needs_comment = CASE WHEN still_present THEN true ELSE b.needs_comment END
MERGE (b)-[:TRIGGERED_BY]->(a)
MERGE (b)-[:SEEN_IN]->(rel)
RETURN b.sig AS sig, b.status AS status, b.count AS count
