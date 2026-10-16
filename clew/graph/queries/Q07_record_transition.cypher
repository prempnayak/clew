// Q07 record_transition
// Purpose: what this action did in this release (procedural memory). Broken edges cost 1000.
// Params: $action, $target, $release, $ok, $error, $ms, $agent, $work_kind, $now
// Callers: clew/explorer/worker.py
MATCH (a:Action {key: $action}), (t:State {key: $target})
MERGE (a)-[l:LEADS_TO {release: $release}]->(t)
SET l.ok = $ok, l.error = $error, l.ms = $ms, l.at = $now, l.by = $agent,
    l.cost = CASE WHEN $ok THEN 1 ELSE 1000 END, l.seen = coalesce(l.seen, 0) + 1
WITH a
SET a.status = CASE WHEN $work_kind IN ['explore', 'mission'] THEN 'done' ELSE a.status END,
    a.tries = a.tries + 1, a.last_result = CASE WHEN $ok THEN 'ok' ELSE 'error' END
RETURN a.key AS action
