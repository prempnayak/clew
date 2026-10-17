// Q56 performed_actions
// Purpose: which explorer executed which action for new work in a session (S5: duplicates across the
//          isolated graphs, where Q32 cannot see the other explorers).
// Params: $session
// Callers: eval/run_baseline.py
MATCH (r:Run)-[p:PERFORMED]->(a:Action)
WHERE r.session = $session AND p.kind IN ['explore', 'mission']
RETURN r.agent AS agent, a.key AS action, min(p.at) AS at
