// Q31 llm_calls_by_session
// Purpose: memory proof: page-reader calls per newly tested action.
// Params: $session
// Callers: clew/api/app.py, eval/run_baseline.py
MATCH (r:Run)-[p:PERFORMED]->(:Action)
WHERE r.session = $session AND p.kind IN ['explore', 'mission']
RETURN r.agent AS agent, count(p) AS actions, max(r.llm_calls) AS llm_calls
