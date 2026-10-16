// Q35 affected_states
// Purpose: pages whose shortest known route passes through an action
//          (run before Q20 marks the action broken, so it reflects the previous release's routes).
// Params: $action
// Callers: clew/scheduler/regressions.py, clew/mcp_server/tools_reporter.py
MATCH (h:State {entry: true, auth: 'out'}), (s:State)
WHERE s <> h
WITH s, shortestPath((h)-[:HAS_ACTION|LEADS_TO*]->(s)) AS p
WHERE p IS NOT NULL AND any(n IN nodes(p) WHERE n.key = $action)
RETURN s.name AS page
