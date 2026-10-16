// Q53 map_growth
// Purpose: first-seen times of pages and actions, for the map-growth chart.
// Params: none
// Callers: clew/api/app.py
MATCH (s:State)
RETURN 'state' AS kind, s.first_seen AS at
UNION ALL
MATCH (a:Action)
RETURN 'action' AS kind, a.created_at AS at
