// Q55 timeline
// Purpose: the most recent steps across all runs (episodic memory, for the timeline).
// Params: $limit
// Callers: clew/api/app.py
MATCH (r:Run)-[p:PERFORMED]->(a:Action)
RETURN r.agent AS agent, r.id AS run, p.n AS n, p.kind AS kind, p.ok AS ok, p.at AS at, a.label AS label,
       a.key AS action
ORDER BY at DESC
LIMIT $limit
