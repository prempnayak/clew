// Q39 pending_jobs
// Purpose: how many jobs of a kind are still queued or claimed for a release (the replay drain check).
// Params: $kind, $release
// Callers: clew/scheduler/watcher.py
MATCH (j:Job {kind: $kind, release: $release})
WHERE j.status IN ['queued', 'claimed']
RETURN count(j) AS pending
