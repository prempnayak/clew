// Q52 state_routes
// Purpose: the route patterns the map has reached (coverage versus /__routes in the scorer).
// Params: none
// Callers: scorer/score.py
MATCH (s:State)
RETURN DISTINCT s.route AS route
