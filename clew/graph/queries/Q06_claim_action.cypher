// Q06 claim_action
// Purpose: the swarm's work splitter. Next untried action: missions first, then the most important page.
//          FalkorDB serializes writes per graph, so two explorers never get the same action.
// Params: $agent, $now, $lease_ms
// Callers: clew/explorer/worker.py
MATCH (s:State)-[:HAS_ACTION]->(a:Action)
WHERE a.status = 'untried' OR (a.status = 'claimed' AND a.claimed_at < $now - $lease_ms)
WITH s, a ORDER BY a.priority DESC, s.importance DESC, a.created_at ASC LIMIT 1
SET a.status = 'claimed', a.claimed_by = $agent, a.claimed_at = $now
RETURN a.key AS action, s.key AS state, a.label AS label, a.origin AS origin, a.next_instance AS instance
