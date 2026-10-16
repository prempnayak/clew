// Q11 repro_steps
// Purpose: shortest route from the logged-out entry page to any trigger of the bug (the repro steps).
//          algo.SPpaths yields nothing when source = target, so a trigger on the entry page is its own branch.
//          The caller takes the row with the lowest cost.
// Params: $sig
// Callers: clew/explorer/worker.py (confirm, verify_fix), clew/mcp_server/tools_reporter.py
MATCH (b:Bug {sig: $sig})-[:TRIGGERED_BY]->(a:Action)<-[:HAS_ACTION]-(h:State {entry: true, auth: 'out'})
WITH a, h LIMIT 1
RETURN [a.key] AS steps, [h.key] AS states, 0.0 AS cost
UNION ALL
MATCH (b:Bug {sig: $sig})-[:TRIGGERED_BY]->(a:Action)<-[:HAS_ACTION]-(s:State)
MATCH (h:State {entry: true, auth: 'out'})
WHERE s <> h
CALL algo.SPpaths({sourceNode: h, targetNode: s, relTypes: ['HAS_ACTION', 'LEADS_TO'],
                   weightProp: 'cost', pathCount: 1})
YIELD path, pathWeight
WITH a, path, pathWeight ORDER BY pathWeight ASC LIMIT 1
RETURN [n IN nodes(path) WHERE n:Action | n.key] + [a.key] AS steps,
       [n IN nodes(path) WHERE n:State | n.key] AS states, pathWeight AS cost
