// Q01 schema
// Purpose: indexes for every key the swarm looks up. One statement per call; "already indexed" errors are ignored.
// Params: none
// Callers: clew/graph/seed.py
CREATE INDEX FOR (s:State) ON (s.key);
CREATE INDEX FOR (a:Action) ON (a.key);
CREATE INDEX FOR (a:Action) ON (a.status);
CREATE INDEX FOR (b:Bug) ON (b.sig);
CREATE INDEX FOR (j:Job) ON (j.id);
CREATE INDEX FOR (j:Job) ON (j.status);
CREATE INDEX FOR (r:Run) ON (r.id);
CREATE INDEX FOR (r:Release) ON (r.name);
CREATE INDEX FOR (m:Mission) ON (m.id);
CREATE INDEX FOR (t:ToolCall) ON (t.id)
