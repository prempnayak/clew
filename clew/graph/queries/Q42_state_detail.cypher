// Q42 state_detail
// Purpose: one page with its actions, their status and the facts about it.
// Params: $key
// Callers: clew/mcp_server/tools_strategist.py, clew/api, clew/explorer/worker.py
MATCH (s:State {key: $key})
OPTIONAL MATCH (s)-[:HAS_ACTION]->(a:Action)
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(s)
RETURN s.key AS key, s.name AS name, s.route AS route, s.auth AS auth, s.url_example AS url,
       s.importance AS importance, s.visits AS visits, s.elements AS elements, s.read AS read,
       s.first_seen AS first_seen, s.first_seen_by AS first_seen_by,
       collect(DISTINCT {key: a.key, label: a.label, role: a.role, name: a.name, kind: a.kind,
                         status: a.status, input_case: a.input_case, priority: a.priority,
                         skip_reason: a.skip_reason, aliases: a.aliases, origin: a.origin}) AS actions,
       collect(DISTINCT f.text) AS facts
