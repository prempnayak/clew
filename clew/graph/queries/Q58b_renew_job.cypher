// Q58b renew_job
// Purpose: the same lease renewal for a job (confirm, replay, verify_fix); nothing returned if the job was lost.
// Params: $id, $agent, $now
// Callers: clew/explorer/worker.py
MATCH (j:Job {id: $id})
WHERE j.status = 'claimed' AND j.claimed_by = $agent
SET j.claimed_at = $now
RETURN j.id AS id
