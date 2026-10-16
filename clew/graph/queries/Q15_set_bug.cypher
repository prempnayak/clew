// Q15 set_bug
// Purpose: status, severity and title changes (confirmed, not_reproduced, …); null leaves a field as it is.
// Params: $sig, $status, $severity, $title, $now
// Callers: clew/explorer/worker.py, clew/mcp_server/tools_reporter.py
MATCH (b:Bug {sig: $sig})
SET b.status = coalesce($status, b.status), b.severity = coalesce($severity, b.severity),
    b.title = coalesce($title, b.title), b.updated_at = $now
RETURN b.sig AS sig, b.status AS status
