# Demo video runbook (about 3 minutes)

Record locally: Docker stack, 4 explorers, LM Studio (Qwen3-8B) or `LLM_BACKEND=off` for a faster take. Every number below was measured on Oct 18 (README, "Results we measured"); **say only numbers you measured in your own take**.

## Before recording (5 minutes)

```bash
make up && make seed                 # stack up, empty map
make reset                           # store back to v1, fresh map
open http://localhost:8082           # war room (API_DEV_PORT)
```

Have a second terminal ready in the repo folder. Zoom the browser so the map and the bug list are readable.

**Two takes make editing easy.** Record S1–S3 in one take. For S4, start from the saved map: `make session N=4 MIN=8 START=v1_snapshot`, then `make deploy-v2`. This needs `make snapshot-v1` after the S1 take.

## Scenes

| Time | Do | Show | Say |
|---|---|---|---|
| 0:00–0:15 | Empty war room | Empty map, idle swarm | "AI testers usually forget everything after each run. Clew's testers share one map in FalkorDB, and every bug comes with the route to reproduce it." |
| 0:15–0:45 | **S1**: header 4 · 10 · shared · fresh map → **Start**. Open Show Cypher → ★ Q06 | Pages appear and grow; explorers `[e1,e2…]` move across the map; the Q06 claim query | "Each explorer claims work in one atomic query, so no two ever do the same thing. Pages on many routes, like the cart, go first: that's betweenness centrality." |
| 0:45–1:20 | Click bugs as they turn **filed** (B2 checkout 500 first, then the coupon) | Bug drawer: repro steps, screenshot, issue body; pipeline confirming → filed | "Every bug is replayed from scratch in a fresh browser before it's reported. The steps are the shortest path through the map." |
| 1:20–1:35 | **S2**: **Kill explorer** (or `make kill-explorer`) | One explorer goes grey; about 2 minutes later its claim is done by another; a new explorer appears | "Its claim simply expires and another explorer finishes the job. No messages between agents: just the graph." |
| 1:35–2:05 | **S3**: `make restart-all`, then Start with **continue map**; click *Your cart (with items)* → **Add mission…** "Test invalid coupon codes" | The map survives the restart; mission actions done in seconds; the LLM chart's bar for S-2 near zero; facts: "save10 → Unknown coupon code" | "Everything restarted, FalkorDB included. New session, no memory in the agents, yet they walk straight to the cart, because the routes live in the graph. Zero page reads." |
| 2:05–2:45 | **S4**: **Deploy v2** | Jobs pending jumps; Release diff fills in: 1 regression (red edge on the map), 1 rename, 1 fixed, new pages; open the regression issue | "Every known route is replayed in parallel. One regression, filed with the route that worked in v1. One renamed button, healed rather than reported. The checkout bug, verified fixed and closed." |
| 2:45–3:00 | README S5 table | Shared vs isolated | "With one shared map versus isolated memories: 215 versus 93 actions covered, zero duplicated work, bugs found about three times faster. Take FalkorDB out and the swarm forgets everything." |

## Measured in the Oct 18 rehearsal (Docker, Qwen3-8B)

- S1: 4/4 bugs, 0 decoys, 0 duplicates, 12/12 route patterns. First sightings: B2 45 s, B1 70 s, B4 122 s, B3 236 s.
- S2: the killed explorer's claim was done by another explorer about 2 minutes later, once its lease expired; executed once.
- S3: the mission (4 cases) was done within 7 s, with 0 page reads.
- S4: one regression issue, filed 3 min 40 s after the deploy; no false regressions; rename healed; B2 fixed and closed.

## Useful during recording

```bash
make logs                                   # everything, live
docker compose logs -f scheduler | grep -E "new_release|replay_jobs|regression"
make score                                  # after the S1 take
```
