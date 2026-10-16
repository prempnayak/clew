// Q25 add_fact
// Purpose: semantic memory; the same fact is stored once.
// Params: $about (state or action key), $kind, $text, $fact_id, $agent, $release, $now
// Callers: clew/explorer/worker.py
MATCH (x) WHERE (x:State OR x:Action) AND x.key = $about
MERGE (f:Fact {kind: $kind, text: $text})
  ON CREATE SET f.id = $fact_id, f.created_by = $agent, f.at = $now, f.release = $release
MERGE (f)-[:ABOUT]->(x)
RETURN f.id AS fact
