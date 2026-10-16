// Q15b record_issue
// Purpose: after the GitHub issue exists (or its dry-run stand-in); releases the Reporter's claim.
// Params: $sig, $number, $url, $title, $body, $now
// Callers: clew/mcp_server/tools_reporter.py
MATCH (b:Bug {sig: $sig})
SET b.status = 'filed', b.reported_status = 'filed', b.issue_number = $number, b.issue_url = $url,
    b.filed_at = $now, b.report_by = NULL, b.issue_title = $title, b.issue_body = $body
RETURN b.issue_number AS issue
