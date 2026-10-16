// Q34b end_session
// Purpose: close a session and keep its summary (coverage, bugs, LLM calls) as a JSON string.
// Params: $id, $summary, $now
// Callers: clew/api/sessions.py
MATCH (s:Session {id: $id})
SET s.status = 'ended', s.ended_at = $now, s.summary = $summary
RETURN s.id AS session
