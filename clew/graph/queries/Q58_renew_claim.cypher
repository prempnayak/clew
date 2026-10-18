// Q58 renew_claim
// Purpose: an explorer still working on an action extends its lease; returns nothing if the claim was lost
//          (the lease expired and another explorer took it), and the explorer then drops the work.
// Params: $action, $agent, $now
// Callers: clew/explorer/worker.py
MATCH (a:Action {key: $action})
WHERE a.status = 'claimed' AND a.claimed_by = $agent
SET a.claimed_at = $now
RETURN a.key AS action
