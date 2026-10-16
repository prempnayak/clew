// Q46 sessions
// Purpose: sessions, newest first.
// Params: none
// Callers: clew/api/sessions.py
MATCH (s:Session)
RETURN s.id AS id, s.release AS release, s.mode AS mode, s.explorers AS explorers, s.minutes AS minutes,
       s.status AS status, s.started_at AS started_at, s.ended_at AS ended_at, s.summary AS summary
ORDER BY started_at DESC
