// Q08 record_run_step
// Purpose: episodic memory: one explorer's trail, one PERFORMED edge per step.
// Params: $action, $run, $agent, $session, $release, $llm_calls, $ok, $ms, $work_kind, $instance, $now
// Callers: clew/explorer/worker.py
MATCH (a:Action {key: $action})
MERGE (r:Run {id: $run})
  ON CREATE SET r.agent = $agent, r.session = $session, r.release = $release,
                r.started_at = $now, r.steps = 0, r.llm_calls = 0
SET r.steps = r.steps + 1, r.llm_calls = r.llm_calls + $llm_calls
CREATE (r)-[:PERFORMED {n: r.steps, at: $now, ok: $ok, ms: $ms, kind: $work_kind, instance: $instance}]->(a)
RETURN r.steps AS steps
