// Q50 missions
// Purpose: missions with their target page and spawned actions.
// Params: none
// Callers: clew/api/missions.py
MATCH (m:Mission)-[:TARGETS]->(s:State)
OPTIONAL MATCH (m)-[:SPAWNED]->(a:Action)
RETURN m.id AS id, m.text AS text, m.status AS status, m.created_by AS created_by, m.created_at AS created_at,
       s.key AS state, s.name AS page, count(a) AS actions,
       sum(CASE WHEN a.status = 'done' THEN 1 ELSE 0 END) AS done
ORDER BY created_at DESC
