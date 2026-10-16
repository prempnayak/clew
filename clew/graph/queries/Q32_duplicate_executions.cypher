// Q32 duplicate_executions
// Purpose: must be empty in shared mode (confirm, replay and variation work excluded).
// Params: $session
// Callers: clew/api/app.py, scorer/score.py, eval/run_baseline.py
MATCH (r:Run)-[p:PERFORMED]->(a:Action)
WHERE r.session = $session AND p.kind IN ['explore', 'mission']
WITH a, count(DISTINCT r.agent) AS agents
WHERE agents > 1
RETURN a.key AS action, agents
