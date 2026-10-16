// Q44b tool_call
// Purpose: one audited tool call.
// Params: $id
// Callers: clew/api/app.py
MATCH (t:ToolCall {id: $id})
OPTIONAL MATCH (t)-[:ABOUT]->(b:Bug)
RETURN t.id AS id, t.tool AS tool, t.agent AS agent, t.args AS args, t.query_ids AS query_ids,
       t.ms AS ms, t.ok AS ok, t.at AS at, t.summary AS summary, b.sig AS bug
