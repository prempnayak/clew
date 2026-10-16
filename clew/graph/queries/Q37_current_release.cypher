// Q37 current_release
// Purpose: the release the graph currently records outcomes for.
// Params: none
// Callers: clew/explorer/worker.py, clew/scheduler/watcher.py, clew/reporter/runner.py, clew/api
MATCH (r:Release {current: true})
RETURN r.name AS release, r.deployed_at AS deployed_at
