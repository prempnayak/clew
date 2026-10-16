// Q41 next_id
// Purpose: per-graph counters for sequential ids (RUN-n, dry-run issue numbers).
// Params: $name
// Callers: clew/explorer/worker.py, clew/reporter/github.py
MERGE (k:Counter {name: $name})
  ON CREATE SET k.v = 0
SET k.v = k.v + 1
RETURN k.v AS v
