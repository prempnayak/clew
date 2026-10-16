// Q43 agents
// Purpose: the swarm panel: every agent with its liveness and current work.
// Params: none
// Callers: clew/api/app.py
MATCH (a:Agent)
RETURN a.name AS name, a.role AS role, a.state AS state, a.current_work AS work,
       a.session AS session, a.last_seen AS last_seen
ORDER BY name
