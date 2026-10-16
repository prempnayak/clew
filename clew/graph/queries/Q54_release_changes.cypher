// Q54 release_changes
// Purpose: what a release changed besides regressions: renames healed, bugs fixed, bugs still present,
//          pages first seen after the deploy.
// Params: $release
// Callers: clew/api/app.py
MATCH (rel:Release {name: $release})
OPTIONAL MATCH (f:Fact {kind: 'rename', release: $release})
WITH rel, collect(DISTINCT f.text) AS renames
OPTIONAL MATCH (fb:Bug)-[:FIXED_IN]->(rel)
WITH rel, renames, collect(DISTINCT {sig: fb.sig, title: fb.title, issue: fb.issue_number}) AS fixed
OPTIONAL MATCH (sb:Bug)-[:SEEN_IN]->(rel) WHERE sb.status <> 'fixed' AND sb.release_found <> $release
WITH rel, renames, fixed, collect(DISTINCT {sig: sb.sig, title: sb.title, issue: sb.issue_number}) AS still
OPTIONAL MATCH (s:State) WHERE s.first_seen >= rel.deployed_at
RETURN renames, fixed, still, collect(DISTINCT {key: s.key, name: s.name}) AS new_pages
