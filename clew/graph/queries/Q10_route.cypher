// Q10 route
// Purpose: cheapest known route between two pages (weighted shortest path); broken edges cost 1000.
//          Also returns the states along the way so the explorer can check for drift after each step.
// Params: $from, $to
// Callers: clew/explorer/route.py
MATCH (src:State {key: $from}), (dst:State {key: $to})
CALL algo.SPpaths({sourceNode: src, targetNode: dst, relTypes: ['HAS_ACTION', 'LEADS_TO'],
                   weightProp: 'cost', pathCount: 1})
YIELD path, pathWeight
RETURN [n IN nodes(path) WHERE n:Action | n.key] AS actions,
       [n IN nodes(path) WHERE n:State | n.key] AS states, pathWeight AS cost
