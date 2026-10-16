// Q29b link_tool_call
// Purpose: when the call was about a bug.
// Params: $id, $sig
// Callers: clew/mcp_server/audit.py
MATCH (t:ToolCall {id: $id}), (b:Bug {sig: $sig})
MERGE (t)-[:ABOUT]->(b)
RETURN t.id AS id
