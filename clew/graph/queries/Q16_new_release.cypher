// Q16 new_release
// Purpose: the release watcher saw /__version change: create the release and link it after the previous one.
// Params: $release, $now
// Callers: clew/scheduler/watcher.py
MATCH (prev:Release {current: true})
WHERE prev.name <> $release
MERGE (next:Release {name: $release})
  ON CREATE SET next.deployed_at = $now
SET prev.current = false, next.current = true
MERGE (prev)-[:NEXT]->(next)
RETURN prev.name AS previous, next.name AS current
