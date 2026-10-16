// Q24 coverage_gaps
// Purpose: the Strategist's view: important pages and how much of each is tested.
// Params: $limit
// Callers: clew/mcp_server/tools_strategist.py
MATCH (s:State)-[:HAS_ACTION]->(a:Action)
WITH s, count(a) AS total,
     sum(CASE WHEN a.status = 'done' THEN 1 ELSE 0 END) AS done,
     sum(CASE WHEN a.kind = 'fill_submit' THEN 1 ELSE 0 END) AS form_cases
RETURN s.key AS state, s.name AS name, s.importance AS importance, total, done, form_cases
ORDER BY importance DESC
LIMIT $limit
