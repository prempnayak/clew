// Q33 bug_feed
// Purpose: the UI's bug list.
// Params: none
// Callers: clew/api/app.py, scorer/score.py
MATCH (b:Bug)-[:TRIGGERED_BY]->(a:Action)<-[:HAS_ACTION]-(s:State)
RETURN b.sig AS sig, b.title AS title, b.kind AS kind, b.severity AS severity, b.status AS status,
       b.issue_number AS issue, b.issue_url AS issue_url, b.first_seen AS first_seen,
       b.release_found AS release_found, collect(DISTINCT s.name) AS pages
ORDER BY first_seen DESC
