// Q22 bug_fixed
// Purpose: a verify_fix replay no longer reproduces the bug.
// Params: $sig, $release, $now
// Callers: clew/explorer/worker.py
MATCH (b:Bug {sig: $sig}), (rel:Release {name: $release})
SET b.status = 'fixed', b.fixed_at = $now
MERGE (b)-[:FIXED_IN]->(rel)
RETURN b.sig AS sig, b.issue_number AS issue
