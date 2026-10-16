// Q45 jobs
// Purpose: the job queue for the UI (most recent first).
// Params: $limit
// Callers: clew/api/app.py
MATCH (j:Job)
RETURN j.id AS id, j.kind AS kind, j.status AS status, j.target AS target, j.release AS release,
       j.claimed_by AS claimed_by, j.claimed_at AS claimed_at, j.attempts AS attempts, j.result AS result,
       j.created_at AS created_at
ORDER BY created_at DESC
LIMIT $limit
