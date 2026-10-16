// Q05 claim_job
// Purpose: confirm, replay and verify_fix jobs come first; expired claims are free again. One atomic query.
// Params: $agent, $now, $lease_ms
// Callers: clew/explorer/worker.py
MATCH (j:Job)
WHERE j.status = 'queued' OR (j.status = 'claimed' AND j.claimed_at < $now - $lease_ms)
WITH j ORDER BY j.priority DESC, j.created_at ASC LIMIT 1
SET j.status = 'claimed', j.claimed_by = $agent, j.claimed_at = $now,
    j.attempts = coalesce(j.attempts, 0) + 1
RETURN j.id AS id, j.kind AS kind, j.target AS target, j.release AS release, j.payload AS payload
