// Q27b link_mission_actions
// Purpose: after Q04 adds the mission's actions (origin 'mission', high priority).
// Params: $mission, $keys
// Callers: clew/api/missions.py, clew/mcp_server/tools_strategist.py
MATCH (m:Mission {id: $mission}), (a:Action) WHERE a.key IN $keys
MERGE (m)-[:SPAWNED]->(a)
RETURN count(a) AS linked
