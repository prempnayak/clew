// Q48 action_outcomes
// Purpose: every recorded outcome of one action, per release, with the route that led there (used to tell a
//          rename from a regression, and by replays to reproduce the original route).
// Params: $action
// Callers: clew/explorer/worker.py
MATCH (a:Action {key: $action})-[l:LEADS_TO]->(t:State)
RETURN l.release AS release, t.key AS target, t.name AS target_name, l.ok AS ok, l.via AS via
