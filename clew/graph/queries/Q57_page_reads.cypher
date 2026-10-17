// Q57 page_reads
// Purpose: how many pages were read (one page-reader run each, LLM or deterministic) in this graph.
// Params: none
// Callers: eval/run_baseline.py
MATCH (s:State)
RETURN sum(CASE WHEN s.read THEN 1 ELSE 0 END) AS reads, count(s) AS states
