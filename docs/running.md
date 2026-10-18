# Running Clew, reading the war room, and checking that the agents use the graph

All commands run in a terminal on the host, from the repo root. The Makefile wraps `docker compose`; you never need to enter a container.

## 1. Start

```bash
cp .env.example .env              # first time only: set passwords and tokens; choose LLM_BACKEND
make up                           # builds and starts FalkorDB, the store, API+UI, MCP, scheduler, reporter, controller
make seed                         # creates nebula_seed and copies it to nebula_live (an empty map)
open http://localhost:8081        # the war room (API_DEV_PORT in .env if 8081 is taken)
```

LLM backends:

- `LLM_BACKEND=openai` with LM Studio running on the host (`OPENAI_BASE_URL=http://host.docker.internal:1234/v1`);
- `vertex` or `gemini_api` for Gemini;
- `off` for the deterministic page reader and template Reporter (fastest; no model needed).

## 2. The scenarios

| Step | Command (or war-room button) | What to watch |
|---|---|---|
| S1 cold exploration | `make session N=4 MIN=10` (header: 4 · 10 · shared · fresh map · **Start**) | The map grows; bugs go suspect → confirming → confirmed → filed |
| S2 kill an explorer | `make kill-explorer` (**Kill explorer**) during the session | One explorer goes grey; its claim is taken by another after the 120 s lease; a new explorer joins |
| Score it | `make score` after the session | Recall vs the hidden answer key, decoys filed, duplicates |
| Save the v1 map | `make snapshot-v1` | Creates `nebula_v1_map` |
| S3 memory | `make restart-all`, then `make session N=4 MIN=6 START=continue`, then click a deep page → **Add mission…** | Mission actions claimed and done in seconds with no page reads; the LLM chart's bar for the session drops |
| S4 new release | while a session runs: `make deploy-v2` (**Deploy v2**) | Release diff: replays, the regression filed, rename healed, B2 fixed and closed, new page |
| Replay S4 quickly | `make session N=4 MIN=8 START=v1_snapshot`, then `make deploy-v2` | Same as S4 without re-running S1 |
| Back to v1 | `make rollback` / `make reset` | |

Other commands: `make logs` (all logs), `make stop` (end a session early), `make replay BUG='<sig>'` (a visible browser replays a bug's steps), `make down` (stop everything; data is kept in Docker volumes).

## 3. Reading the war room

| Panel | What it shows | Where it comes from |
|---|---|---|
| Header | Graph, release, running session and time left; LLM backend and filing mode | Q37, Q46 |
| **Swarm** (left) | Each explorer, what it is working on now (`explore → …`, `confirm → …`, `replay → …`), last seen; grey = dead. Below: pages, actions done/total, claims held now, jobs pending, **Duplicates (Q32)** (0 in shared mode) | Q43 heartbeats, Q23, Q45, Q32 |
| **Live map** (centre) | One node per kind of page. Size = betweenness; green = all actions tested, amber = untried work; red ring = a bug there; red edge = broken in this release; dashed = previous release only; `[e1,e3]` = explorers working there now. Click a page for its actions, facts and "Add mission" | Q47, Q30, Q42 |
| Charts | Map growth; page-reader calls per newly tested action, per session | Q53, Q31, Q51 |
| **Bugs** (right) | The pipeline (suspect → new → confirming → confirmed → filed → fixed). Click a bug: signature, **repro steps (shortest path, Q11)**, evidence and screenshot, issue body | Q33, Q38, Q11 |
| **Release diff** | After a deploy: regressions (broken / moved, filed), changed layouts (not filed), renames healed, fixed, still present, new pages, replays pending | Q19, Q54, Q39 |
| **Show Cypher** | ★ the key queries; every Reporter tool call with the queries it ran, their parameters and first rows | `/api/queries`, ToolCall nodes (Q44) |
| Memory: facts | What the swarm learned | Q26 |

Suspects (console errors, problems seen while replaying) are counted but never filed.

## 4. Checking that the agents navigate by the graph

The explorers keep nothing between work items: every item starts in a fresh browser at the entry page and gets its route from FalkorDB.

**a. Watch the queries live.** Every claim, route and record is a `GRAPH.QUERY` / `GRAPH.RO_QUERY`:

```bash
docker compose exec falkordb sh -c 'redis-cli -a "$FALKORDB_PASSWORD" --no-auth-warning MONITOR' | grep -E "GRAPH\.(RO_)?QUERY" | cut -c1-220
```

**b. The event stream** the UI listens to:

```bash
docker compose exec falkordb sh -c 'redis-cli -a "$FALKORDB_PASSWORD" --no-auth-warning SUBSCRIBE clew:nebula_live:events'
```

**c. One explorer's log:** claims, drift and re-planning, pages read, bugs.

```bash
docker ps --filter label=clew.role=explorer --format '{{.Names}}'
docker logs -f <name>
```

**d. Query the graph** in the FalkorDB Browser at http://localhost:3001 (`FALKORDB_BROWSER_PORT`). Connect to host `localhost`, port `6379`, with the password from `.env`, and select graph `nebula_live`.

```cypher
// the map as a picture
MATCH p=(:State)-[:HAS_ACTION]->(:Action)-[:LEADS_TO]->(:State) RETURN p LIMIT 150

// who holds which claim right now (leases)
MATCH (s:State)-[:HAS_ACTION]->(a:Action {status: 'claimed'}) RETURN a.claimed_by, s.name, a.label, a.claimed_at

// the route the workers would walk to a page (the same weighted shortest path, Q10)
MATCH (src:State {entry: true, auth: 'out'}), (dst:State) WHERE dst.name STARTS WITH 'Your cart'
CALL algo.SPpaths({sourceNode: src, targetNode: dst, relTypes: ['HAS_ACTION','LEADS_TO'], weightProp: 'cost', pathCount: 1})
YIELD path, pathWeight RETURN dst.name, [n IN nodes(path) WHERE n:Action | n.label] AS steps, pathWeight

// every bug, its trigger and issue
MATCH (b:Bug)-[:TRIGGERED_BY]->(a:Action)<-[:HAS_ACTION]-(s:State)
RETURN b.status, b.title, s.name AS page, a.label AS action, b.issue_number

// one explorer's trail (episodic memory)
MATCH (r:Run)-[p:PERFORMED]->(a:Action) RETURN r.agent, p.n, p.kind, p.ok, a.label ORDER BY r.agent, p.n

// actions executed by more than one explorer (should be empty)
MATCH (r:Run)-[p:PERFORMED]->(a:Action) WHERE p.kind IN ['explore','mission']
WITH a, count(DISTINCT r.agent) AS n WHERE n > 1 RETURN a.key, n
```

The same queries from the terminal:

```bash
docker compose exec falkordb sh -c 'redis-cli -a "$FALKORDB_PASSWORD" --no-auth-warning GRAPH.QUERY nebula_live "MATCH (b:Bug) RETURN b.status, b.title"'
```

**e. The API:** http://localhost:8081/api/docs lists every endpoint behind the war room (`/api/bugs`, `/api/agents`, `/api/jobs`, `/api/sessions`, `/api/timeline`, `/api/diff`).

**f. The removal test:** `docker compose stop falkordb`. The explorers can't claim, route or record, and the swarm stops. `docker compose start falkordb` and they continue from the persisted map.
