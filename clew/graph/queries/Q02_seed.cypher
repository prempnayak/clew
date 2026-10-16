// Q02 seed
// Purpose: App and first release; states are created by explorers when they see them.
// Params: $app, $base_url, $release, $now
// Callers: clew/graph/seed.py
MERGE (app:App {name: $app})
SET app.base_url = $base_url
MERGE (rel:Release {name: $release})
  ON CREATE SET rel.deployed_at = $now
SET rel.current = true
RETURN app.name AS app, rel.name AS release
