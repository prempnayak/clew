// Q20 mark_broken
// Purpose: routes avoid this action from now on (all of its LEADS_TO edges cost 1000).
// Params: $action
// Callers: clew/scheduler/regressions.py
MATCH (a:Action {key: $action})-[l:LEADS_TO]->()
SET l.cost = 1000
RETURN count(l) AS edges
