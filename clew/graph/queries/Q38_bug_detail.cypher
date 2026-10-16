// Q38 bug_detail
// Purpose: one bug with its triggers, releases and look-alikes (get_bug, bug detail panel, confirm jobs).
// Params: $sig
// Callers: clew/mcp_server/tools_reporter.py, clew/explorer/worker.py, clew/api
MATCH (b:Bug {sig: $sig})
OPTIONAL MATCH (b)-[:TRIGGERED_BY]->(a:Action)<-[:HAS_ACTION]-(s:State)
OPTIONAL MATCH (b)-[:SEEN_IN]->(r:Release)
OPTIONAL MATCH (b)-[:FIXED_IN]->(fr:Release)
OPTIONAL MATCH (b)-[:SAME_AS]->(o:Bug)
RETURN b.sig AS sig, b.kind AS kind, b.title AS title, b.status AS status, b.severity AS severity,
       b.evidence AS evidence, b.count AS count, b.first_seen AS first_seen, b.last_seen AS last_seen,
       b.release_found AS release_found, b.issue_number AS issue, b.issue_url AS issue_url,
       b.issue_title AS issue_title, b.issue_body AS issue_body,
       collect(DISTINCT a.key) AS triggers, collect(DISTINCT s.name) AS pages,
       collect(DISTINCT s.importance) AS importance, collect(DISTINCT r.name) AS seen_in,
       collect(DISTINCT fr.name) AS fixed_in, collect(DISTINCT o.sig) AS same_as
