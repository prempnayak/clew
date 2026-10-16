// Q19 regressions
// Purpose: per-release edge diff. An action regressed when it worked in the previous release and none of its
//          outcomes in the new release is a working edge to a page it reached before. Actions that already
//          failed somewhere in the previous release are skipped: their outcome depended on hidden state
//          (e.g. an empty cart), so a change there is not evidence of a regression (docs/decisions.md).
// Params: $previous, $release
// Callers: clew/scheduler/regressions.py, clew/mcp_server/tools_reporter.py (release_diff), clew/api
MATCH (s:State)-[:HAS_ACTION]->(a:Action)-[was:LEADS_TO {release: $previous}]->(t1:State)
WITH s, a, collect(DISTINCT CASE WHEN was.ok THEN t1.key END) AS ok_before,
     collect(DISTINCT CASE WHEN was.ok THEN t1.name END) AS names_before,
     sum(CASE WHEN was.ok THEN 0 ELSE 1 END) AS failed_before
WHERE failed_before = 0 AND size(ok_before) > 0
MATCH (a)-[now:LEADS_TO {release: $release}]->(t2:State)
WITH s, a, ok_before, names_before,
     collect({key: t2.key, name: t2.name, ok: now.ok, error: now.error}) AS after
WHERE none(x IN after WHERE x.ok AND x.key IN ok_before)
RETURN a.key AS action, s.name AS page, a.label AS label, names_before[0] AS was_target,
       ok_before[0] AS was_target_key, after[0].name AS now_target, after[0].key AS now_target_key,
       after[0].ok AS ok, after[0].error AS error
