// Q09 importance
// Purpose: betweenness centrality over the state graph; pages on many routes get tested first.
//          Betweenness is sampled and the default seed is time-based, so a fixed seed keeps priorities stable.
// Params: none
// Callers: clew/scheduler/importance.py
CALL algo.betweenness({nodeLabels: ['State', 'Action'], relationshipTypes: ['HAS_ACTION', 'LEADS_TO'],
                       samplingSize: 512, samplingSeed: 42})
YIELD node, score
WITH node, score WHERE node:State
SET node.importance = score
RETURN count(node) AS states
