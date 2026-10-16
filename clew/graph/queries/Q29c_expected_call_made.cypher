// Q29c expected_call_made
// Purpose: the Reporter's runner: did this turn make a successful call of an expected tool?
// Params: $sig, $tools, $since
// Callers: clew/reporter/runner.py
MATCH (b:Bug {sig: $sig})
OPTIONAL MATCH (t:ToolCall)-[:ABOUT]->(b)
WHERE t.tool IN $tools AND t.ok = true AND t.at >= $since
RETURN count(t) > 0 AS made
