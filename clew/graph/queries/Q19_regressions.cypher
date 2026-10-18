// Q19 regressions
// Purpose: per-release edge diff. For every action that worked in the previous release and has no working edge
//          in the new release to a page it reached before, `change` says how it differs:
//          'broken'  = it now fails (error, missing element);
//          'moved'   = it works but lands on a different page (route) than before;
//          'variant' = it lands on the same page (route) with a different layout, usually different data behind
//                      it (an empty list for another account). Variants are shown in the diff but not filed.
//          Actions that already failed somewhere in the previous release are skipped: their outcome depended on
//          hidden state, so a change there is not evidence of a regression (docs/decisions.md).
// Params: $previous, $release
// Callers: clew/scheduler/regressions.py, clew/mcp_server/tools.py (release_diff), clew/api/app.py
MATCH (s:State)-[:HAS_ACTION]->(a:Action)-[was:LEADS_TO {release: $previous}]->(t1:State)
WITH s, a, collect(DISTINCT CASE WHEN was.ok THEN t1.key END) AS ok_before,
     collect(DISTINCT CASE WHEN was.ok THEN t1.route END) AS routes_before,
     collect(DISTINCT CASE WHEN was.ok THEN t1.name END) AS names_before,
     sum(CASE WHEN was.ok THEN 0 ELSE 1 END) AS failed_before
WHERE failed_before = 0 AND size(ok_before) > 0
MATCH (a)-[now:LEADS_TO {release: $release}]->(t2:State)
WITH s, a, ok_before, routes_before, names_before,
     collect({key: t2.key, route: t2.route, name: t2.name, ok: now.ok, error: now.error}) AS after
WHERE none(x IN after WHERE x.ok AND x.key IN ok_before)
WITH s, a, ok_before, names_before, after,
     CASE WHEN any(x IN after WHERE NOT x.ok) THEN 'broken'
          WHEN any(x IN after WHERE x.route IN routes_before) THEN 'variant'
          ELSE 'moved' END AS change
RETURN a.key AS action, s.name AS page, a.label AS label, change, names_before[0] AS was_target,
       ok_before[0] AS was_target_key, after[0].name AS now_target, after[0].key AS now_target_key,
       after[0].ok AS ok, after[0].error AS error
