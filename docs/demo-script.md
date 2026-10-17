# Demo runbook (video, about 3 minutes)

Scenes follow handoff §23.2. Times are what we measured locally with 4 explorers. With a local 8B model, page reads take 3–18 s each, so S1 takes longer than with Gemini or with `LLM_BACKEND=off`. **Say only numbers you measured** (`make score`, `make baseline`).

## Before recording

```bash
make up && make seed            # stack up, empty map
make reset                      # store back to v1, fresh map
open http://localhost:8081      # war room (API_DEV_PORT)
```

For a fast S4 take without re-running S1: `make session START=v1_snapshot` (needs `make snapshot-v1` after a full S1).

## Scenes

| Time | Do | Show | Say |
|---|---|---|---|
| 0:00–0:15 | Empty map | Idle war room | "AI testers usually forget everything after each run. Ours share one map, and every bug comes with the route to reproduce it." |
| 0:15–0:45 | **S1**: Start (4 explorers, 10 min, fresh map) | The map grows; open Show Cypher → ★ Q06 | "Each explorer claims work in one atomic query, so no two ever test the same thing. Pages on many routes, like the cart, go first: that's betweenness centrality (Q09)." |
| 0:45–1:20 | Click the bugs as they turn *filed* | Bug drawer: repro steps (Q11), screenshot, issue body | "Every bug is replayed from scratch in a fresh browser before anyone hears about it. The steps are the shortest path through the map." |
| 1:20–1:35 | **S2**: Kill explorer | Swarm: one explorer goes grey; after the 120 s lease its claim is taken by another; a new explorer joins | "Its claim expires and someone else finishes the job. No messages, just the graph." |
| 1:35–2:05 | **S3**: `make restart-all`, then Start with *continue map*; open *Your cart (with items)*, "Add mission…": "Test invalid coupon codes" | Mission actions claimed at once and done in seconds; Facts panel shows "save10 → Unknown coupon code"; LLM chart: S-2 has 0 page-reader calls | "New session, zero memory in the agents, yet they walk straight to the cart: the routes are in FalkorDB." |
| 2:05–2:45 | **S4**: Deploy v2 | Release diff: 1 regression (R1, red edge on the map), 1 rename healed, B2 fixed; issue drawer of the regression | "Every known route is replayed in parallel. One regression, filed with the route that worked yesterday. One renamed button, healed rather than reported. The checkout bug, verified fixed and closed." |
| 2:45–3:00 | S5 table (`eval/results/baseline.md`) | README table | "With one shared map versus isolated memories: [measured numbers]. Take FalkorDB out and the swarm forgets everything." |

## Commands behind the buttons

```bash
make session N=4 MIN=10                 # S1 (fresh map)
make kill-explorer                      # S2
make restart-all                        # S3 (FalkorDB included)
make session N=4 MIN=5 START=continue   # S3, second session
make mission STATE='/cart|out|873cfbbf' TEXT='Test invalid coupon codes'
make snapshot-v1                        # after S1, for quick S4 takes
make deploy-v2                          # S4 (make rollback to undo)
make score                              # recall, decoys, coverage, duplicates
make replay BUG='<sig>'                 # replay a bug's steps in a visible browser
```

## Checklist after each take

- [ ] `make score`: recall, 0 decoys, duplicate executions 0.
- [ ] Issue bodies have numbered steps that replay (`make replay BUG=…`).
- [ ] S4: the regression issue was filed within about 5 minutes of the deploy (measured 2 min 48 s on Oct 17).
