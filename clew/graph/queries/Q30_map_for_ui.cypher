// Q30 map_for_ui
// Purpose: page-to-page edges for the live map (Action nodes folded into edge labels).
// Params: $release
// Callers: clew/api/app.py
MATCH (s:State)-[:HAS_ACTION]->(a:Action)-[l:LEADS_TO]->(t:State)
WHERE l.release = $release
RETURN s.key AS source, t.key AS target, a.label AS action, a.key AS action_key, l.ok AS ok, l.cost AS cost
