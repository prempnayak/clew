// Q14 finish_job
// Purpose: only the claimant can finish a job.
// Params: $id, $agent, $status, $result, $now
// Callers: clew/explorer/worker.py
MATCH (j:Job {id: $id}) WHERE j.claimed_by = $agent
SET j.status = $status, j.result = $result, j.finished_at = $now
RETURN j.id AS id
