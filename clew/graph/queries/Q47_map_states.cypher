// Q47 map_states
// Purpose: pages for the live map: size = importance, colour = untried work, badge = bugs.
// Params: none
// Callers: clew/api/app.py
MATCH (s:State)
OPTIONAL MATCH (s)-[:HAS_ACTION]->(a:Action)
OPTIONAL MATCH (b:Bug)-[:TRIGGERED_BY]->(a)
WITH s, count(DISTINCT a) AS actions,
     count(DISTINCT CASE WHEN a.status IN ['untried', 'claimed'] THEN a END) AS open,
     count(DISTINCT CASE WHEN b.status <> 'not_reproduced' THEN b END) AS bugs
RETURN s.key AS key, s.name AS name, s.route AS route, s.auth AS auth, s.importance AS importance,
       s.entry AS entry, s.first_seen AS first_seen, actions, open, bugs
