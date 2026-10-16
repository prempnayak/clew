// Q51 session_stats
// Purpose: per-session totals for the S5 table: steps by kind, unique actions, page-reader calls.
// Params: $session
// Callers: eval/run_baseline.py, clew/api/sessions.py
MATCH (r:Run {session: $session})
OPTIONAL MATCH (r)-[p:PERFORMED]->(a:Action)
WITH collect(DISTINCT r) AS runs, count(p) AS steps,
     sum(CASE WHEN p.kind IN ['explore', 'mission'] THEN 1 ELSE 0 END) AS explore_steps,
     count(DISTINCT CASE WHEN p.kind IN ['explore', 'mission'] THEN a END) AS unique_actions
RETURN size(runs) AS runs, steps, explore_steps, unique_actions,
       reduce(t = 0, r IN runs | t + r.llm_calls) AS llm_calls
