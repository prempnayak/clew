// Q27 add_mission
// Purpose: a human or the Strategist asks for targeted testing of a page.
// Params: $state, $text, $by, $now
// Callers: clew/api/missions.py, clew/mcp_server/tools_strategist.py
MATCH (s:State {key: $state})
MERGE (k:Counter {name: 'mission'})
  ON CREATE SET k.v = 0
SET k.v = k.v + 1
CREATE (m:Mission {id: 'M-' + toString(k.v), text: $text, status: 'open', created_by: $by,
                   created_at: $now})-[:TARGETS]->(s)
RETURN m.id AS mission
