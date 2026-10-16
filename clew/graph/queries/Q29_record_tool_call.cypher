// Q29 record_tool_call
// Purpose: written by the MCP server for every tool call (audit trail behind Show Cypher).
// Params: $id, $tool, $agent, $args, $query_ids, $ms, $ok, $summary, $now
// Callers: clew/mcp_server/audit.py
CREATE (t:ToolCall {id: $id, tool: $tool, agent: $agent, args: $args, query_ids: $query_ids,
                    ms: $ms, ok: $ok, at: $now, summary: $summary})
RETURN t.id AS id
