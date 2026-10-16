// Q23 coverage
// Purpose: counts for the UI's swarm panel.
// Params: none
// Callers: clew/scheduler/watcher.py, clew/api, clew/mcp_server (map_summary)
OPTIONAL MATCH (a:Action)
WITH count(a) AS actions,
     sum(CASE WHEN a.status = 'done' THEN 1 ELSE 0 END) AS done,
     sum(CASE WHEN a.status = 'untried' THEN 1 ELSE 0 END) AS untried,
     sum(CASE WHEN a.status = 'claimed' THEN 1 ELSE 0 END) AS claimed
OPTIONAL MATCH (s:State)
WITH actions, done, untried, claimed, count(s) AS states
OPTIONAL MATCH (b:Bug)
RETURN states, actions, done, untried, claimed, count(b) AS bugs
