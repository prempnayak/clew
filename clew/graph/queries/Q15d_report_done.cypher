// Q15d report_done
// Purpose: the Reporter's runner, after a successful turn: what was reported now matches the status.
// Params: $sig, $agent, $now
// Callers: clew/reporter/runner.py
MATCH (b:Bug {sig: $sig}) WHERE b.report_by = $agent
SET b.reported_status = b.status, b.needs_comment = false, b.report_by = NULL, b.reported_at = $now
RETURN b.sig AS sig, b.reported_status AS reported_status
