// Q28 agent_heartbeat
// Purpose: liveness and current work of an agent, for the swarm panel.
// Params: $name, $role, $model, $session, $state, $work, $now
// Callers: clew/explorer/worker.py, clew/reporter/runner.py, clew/scheduler/watcher.py
MERGE (a:Agent {name: $name})
SET a.role = $role, a.model = $model, a.session = $session, a.state = $state,
    a.current_work = $work, a.last_seen = $now
RETURN a.name AS agent
