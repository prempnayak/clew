// Q18 enqueue_verify_fix
// Purpose: re-check every filed bug on the new release.
// Params: $release, $now
// Callers: clew/scheduler/watcher.py
MATCH (b:Bug) WHERE b.status IN ['filed', 'confirmed']
  AND NOT (:Job {kind: 'verify_fix', release: $release})-[:FOR]->(b)
WITH collect(b) AS bugs
MERGE (k:Counter {name: 'job'})
  ON CREATE SET k.v = 0
WITH k, bugs, k.v AS base
SET k.v = base + size(bugs)
WITH base, bugs
UNWIND range(0, size(bugs) - 1) AS i
WITH base + i + 1 AS n, bugs[i] AS b
CREATE (j:Job {id: 'J-' + toString(n), kind: 'verify_fix', status: 'queued', target: b.sig,
               release: $release, priority: 60, created_at: $now})-[:FOR]->(b)
RETURN count(j) AS queued
