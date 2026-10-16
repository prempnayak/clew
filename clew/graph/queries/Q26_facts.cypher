// Q26 facts
// Purpose: context for the page reader and the Strategist (semantic memory read).
// Params: $kinds, $limit
// Callers: clew/explorer/page_reader.py, clew/mcp_server/tools_strategist.py, clew/api
MATCH (f:Fact)-[:ABOUT]->(x)
WHERE f.kind IN $kinds
RETURN f.kind AS kind, f.text AS text, x.key AS about, f.at AS at
ORDER BY at DESC
LIMIT $limit
