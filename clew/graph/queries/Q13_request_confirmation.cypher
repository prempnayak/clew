// Q13 request_confirmation
// Purpose: creates exactly one confirm job per new bug (a suspect needs a rule or a human first).
// Params: $sig, $release, $payload, $now
// Callers: clew/reporter/runner.py
MATCH (b:Bug {sig: $sig}) WHERE b.status = 'new'
MERGE (k:Counter {name: 'job'})
  ON CREATE SET k.v = 0
SET k.v = k.v + 1, b.status = 'confirming'
CREATE (j:Job {id: 'J-' + toString(k.v), kind: 'confirm', status: 'queued', target: $sig,
               release: $release, priority: 100, created_at: $now, payload: $payload})-[:FOR]->(b)
RETURN j.id AS job
