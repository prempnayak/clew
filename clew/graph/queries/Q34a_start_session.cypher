// Q34a start_session
// Purpose: a numbered session (S-n) on the shared map.
// Params: $release, $mode, $explorers, $minutes, $start_from, $now
// Callers: clew/api/sessions.py
MERGE (k:Counter {name: 'session'})
  ON CREATE SET k.v = 0
SET k.v = k.v + 1
CREATE (s:Session {id: 'S-' + toString(k.v), release: $release, mode: $mode, explorers: $explorers,
                   minutes: $minutes, start_from: $start_from, started_at: $now, status: 'running'})
RETURN s.id AS session
