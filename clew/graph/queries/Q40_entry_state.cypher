// Q40 entry_state
// Purpose: the logged-out entry page every fresh browser context starts from.
// Params: none
// Callers: clew/explorer/worker.py, clew/api
MATCH (s:State {entry: true, auth: 'out'})
RETURN s.key AS key
ORDER BY key
LIMIT 1
