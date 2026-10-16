// Q36b mark_same_as
// Purpose: the Reporter merges a look-alike signature into an existing bug instead of filing it.
// Params: $sig, $other, $reason, $now
// Callers: clew/mcp_server/tools_reporter.py
MATCH (b:Bug {sig: $sig}), (other:Bug {sig: $other})
WHERE b <> other
MERGE (b)-[r:SAME_AS]->(other)
  ON CREATE SET r.reason = $reason, r.at = $now
RETURN b.sig AS sig, other.sig AS same_as
