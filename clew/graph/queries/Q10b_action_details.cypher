// Q10b action_details
// Purpose: how to perform each step (the caller restores the route's order).
// Params: $keys
// Callers: clew/explorer/route.py, clew/mcp_server/tools_reporter.py
MATCH (a:Action) WHERE a.key IN $keys
RETURN a.key AS key, a.label AS label, a.kind AS kind, a.by AS by, a.selector AS selector,
       a.inputs AS inputs, a.instance_policy AS instance_policy, a.state_key AS state,
       a.role AS role, a.name AS name, a.aliases AS aliases, a.input_case AS input_case
