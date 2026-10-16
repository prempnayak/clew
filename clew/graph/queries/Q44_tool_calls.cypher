// Q44 tool_calls
// Purpose: recent audited tool calls for the Show Cypher drawer.
// Params: $limit
// Callers: clew/api/app.py
MATCH (t:ToolCall)
RETURN t.id AS id, t.tool AS tool, t.agent AS agent, t.args AS args, t.query_ids AS query_ids,
       t.ms AS ms, t.ok AS ok, t.at AS at, t.summary AS summary
ORDER BY at DESC
LIMIT $limit
