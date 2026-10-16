// Q03b claim_read
// Purpose: exactly one explorer reads a new page with the LLM (a read lock with a lease).
// Params: $key, $agent, $now, $lease_ms
// Callers: clew/explorer/worker.py
MATCH (s:State {key: $key})
WHERE s.read = false AND (s.read_by IS NULL OR s.read_at < $now - $lease_ms)
SET s.read_by = $agent, s.read_at = $now
RETURN s.key AS key
