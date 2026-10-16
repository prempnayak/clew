// Q49 previous_release
// Purpose: the release before the current one (NEXT chain).
// Params: none
// Callers: clew/scheduler/watcher.py, clew/api
MATCH (p:Release)-[:NEXT]->(c:Release {current: true})
RETURN p.name AS previous, c.name AS current
