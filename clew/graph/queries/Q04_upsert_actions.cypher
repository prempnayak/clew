// Q04 upsert_actions
// Purpose: the page reader's output; marks the page as read even if it has no actions.
//          HAS_ACTION edges cost 0, so a route's cost is its number of steps.
// Params: $state, $name (nullable), $actions (list of maps: key, label, role, name, by, selector, kind,
//         input_case, inputs, instance_policy, status, skip_reason, priority, origin), $now
// Callers: clew/explorer/worker.py, clew/mcp_server/tools_strategist.py, clew/api/missions.py
MATCH (s:State {key: $state})
SET s.read = true, s.name = coalesce($name, s.name)
WITH s
UNWIND $actions AS act
MERGE (a:Action {key: act.key})
  ON CREATE SET a.state_key = $state, a.label = act.label, a.role = act.role, a.name = act.name,
                a.by = act.by, a.selector = act.selector, a.kind = act.kind,
                a.input_case = act.input_case, a.inputs = act.inputs,
                a.instance_policy = act.instance_policy, a.next_instance = 0,
                a.status = coalesce(act.status, 'untried'), a.skip_reason = act.skip_reason,
                a.tries = 0, a.priority = act.priority, a.origin = act.origin,
                a.aliases = [], a.created_at = $now
MERGE (s)-[h:HAS_ACTION]->(a)
  ON CREATE SET h.cost = 0
RETURN count(a) AS added
