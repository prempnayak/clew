// Q06b claim_variation
// Purpose: when nothing is untried, re-run a link-group action on its next instance (finds data-dependent bugs).
// Params: $agent, $now, $lease_ms
// Callers: clew/explorer/worker.py
MATCH (s:State)-[:HAS_ACTION]->(a:Action)
WHERE a.status = 'done' AND a.instance_policy = 'round_robin'
  AND (a.varied_by IS NULL OR a.varied_at < $now - $lease_ms)
WITH s, a ORDER BY coalesce(a.variations, 0) ASC, s.importance DESC LIMIT 1
SET a.varied_by = $agent, a.varied_at = $now, a.variations = coalesce(a.variations, 0) + 1,
    a.next_instance = a.next_instance + 1
RETURN a.key AS action, s.key AS state, a.next_instance AS instance
