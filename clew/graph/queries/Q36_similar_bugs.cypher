// Q36 similar_bugs
// Purpose: other bugs on the same page (memory for the Reporter's merge decisions).
//          same_trigger is true when the other bug was triggered by the same action.
// Params: $sig
// Callers: clew/mcp_server/tools_reporter.py, clew/reporter/runner.py
MATCH (b:Bug {sig: $sig})-[:TRIGGERED_BY]->(:Action)<-[:HAS_ACTION]-(s:State)
MATCH (s)-[:HAS_ACTION]->(oa:Action)<-[:TRIGGERED_BY]-(other:Bug)
WHERE other.sig <> b.sig
RETURN DISTINCT other.sig AS sig, other.title AS title, other.status AS status, other.kind AS kind,
       size((b)-[:TRIGGERED_BY]->(oa)) > 0 AS same_trigger
