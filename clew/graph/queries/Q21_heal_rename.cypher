// Q21 heal_rename
// Purpose: same role, new name, same destination: update the selector and remember the rename.
// Params: $action, $new_name, $new_label, $selector, $text, $fact_id, $agent, $release, $now
// Callers: clew/explorer/worker.py
MATCH (a:Action {key: $action})
SET a.aliases = a.aliases + [a.name], a.name = $new_name, a.label = $new_label,
    a.selector = $selector, a.healed_at = $now
WITH a
MERGE (f:Fact {kind: 'rename', text: $text})
  ON CREATE SET f.id = $fact_id, f.created_by = $agent, f.at = $now, f.release = $release
MERGE (f)-[:ABOUT]->(a)
RETURN f.id AS fact
