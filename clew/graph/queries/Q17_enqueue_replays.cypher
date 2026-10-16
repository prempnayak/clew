// Q17 enqueue_replays
// Purpose: one replay job per working transition of the previous release, shallow first.
//          Safe to re-run: skips actions already replayed or queued for this release.
//          IDs: read the counter once and add the row index (SET runs eagerly, so per-row counters repeat).
// Params: $previous, $release, $now
// Callers: clew/scheduler/watcher.py
MATCH (h:State {entry: true, auth: 'out'})
MATCH (s:State)-[:HAS_ACTION]->(a:Action)-[l:LEADS_TO {release: $previous}]->(:State)
WHERE l.ok = true AND NOT (a)-[:LEADS_TO {release: $release}]->()
  AND NOT (:Job {kind: 'replay', release: $release})-[:FOR]->(a)
WITH DISTINCT h, s, a
WITH a, CASE WHEN s = h THEN 0 ELSE length(shortestPath((h)-[:HAS_ACTION|LEADS_TO*]->(s))) END AS depth
WITH collect({action: a, depth: depth}) AS work
MERGE (k:Counter {name: 'job'})
  ON CREATE SET k.v = 0
WITH k, work, k.v AS base
SET k.v = base + size(work)
WITH base, work
UNWIND range(0, size(work) - 1) AS i
WITH base + i + 1 AS n, work[i].action AS a, work[i].depth AS depth
CREATE (j:Job {id: 'J-' + toString(n), kind: 'replay', status: 'queued', target: a.key,
               release: $release, priority: 50 - coalesce(depth, 40), created_at: $now})-[:FOR]->(a)
RETURN count(j) AS queued
