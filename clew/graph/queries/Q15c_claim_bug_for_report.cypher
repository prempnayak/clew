// Q15c claim_bug_for_report
// Purpose: the Reporter's queue: status changes it hasn't handled, or pending comments. One atomic claim.
// Params: $statuses, $agent, $now, $lease_ms
// Callers: clew/reporter/runner.py
MATCH (b:Bug)
WHERE ((b.status IN $statuses AND coalesce(b.reported_status, '') <> b.status) OR b.needs_comment = true)
  AND (b.report_by IS NULL OR b.report_at < $now - $lease_ms)
WITH b ORDER BY b.first_seen ASC LIMIT 1
SET b.report_by = $agent, b.report_at = $now
RETURN b.sig AS sig, b.status AS status, b.needs_comment AS needs_comment
