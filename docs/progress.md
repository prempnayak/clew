# Build progress (kept current so anyone can pick up where the last session stopped)

Last updated: 2026-10-17 (Sat), during the Claude Code build session.

## Done (all committed and pushed to origin/main)

- **M0/M1:** store, query library Q01–Q55 (V1 on 4.18.3 + 4.22.1), fingerprint and extraction on 54 real snapshots (V2), explorer worker, oracles, page reader.
- **M2:** MCP server and audited tools, Reporter, GitHub client (dry run), release watcher, regression pipeline. Locally: 4 explorers confirm and file B1–B4 with 0 duplicates; S4 run files R1, heals the rename, verifies B2 fixed, finds Gift cards. Integration test passes (`make test-integration`, ~6.5 min).
- **M3:** API, SSE, Show Cypher, controller, CLI, war-room UI, Dockerfiles, Compose, Caddy, Makefile. Images build (V3 ✅: Playwright 1.63.0 image); the answer key is absent from the shop and app images; `make up` + `make seed` work (V13: data dir `/var/lib/falkordb/data`).

## Next (in order)

1. In Docker: `make session N=4 MIN=5` → check the controller scales explorers (V12), then `make kill-explorer` (S2), `make restart-all` + mission (S3), `make deploy-v2` (S4). Local `.env` uses host ports 6391/3001/8095/8010/8082 (UI at http://localhost:8082).
2. Scorer (`scorer/score.py`: planted_bugs.yaml + /__routes + Q33/Q52/Q32) and `eval/run_baseline.py` (S5 shared vs isolated).
3. README (setup, graph model, Cypher list, tracks, AI disclosure), `docs/graph-model.md`; `make docs` already generates `docs/cypher.md`.
4. Optional: Strategist runner (cut list #1; missions use the deterministic fallback in `clew/api/ops.py`), CI workflow.

## Needs a human

- Gemini credentials (V7, V8): set `LLM_BACKEND=vertex` + project, or `gemini_api` + key. Until then everything runs on the deterministic reader and writer.
- GitHub token for real issues (V11): fine-grained, Issues on the issues repo only; `make github-labels`.
- GCP VM deploy (§21), demo video, blog, submission form, Discord questions (V14).

## Dev setup used in this session

- Store: `SHOP_DB=artifacts/dev.db SHOP_ADMIN_TOKEN=devtoken SHOP_EXPLORER_PASSWORD=pw uv run uvicorn shop.app:app --port 8090`
- FalkorDB: `docker run -d --name clew-falkordb-dev -p 127.0.0.1:6390:6379 falkordb/falkordb:v4.22.1`
- Env: `source artifacts/dev.env` (FALKORDB_PORT=6390, CLEW_GRAPH=nebula_dev, LLM_BACKEND=off)
- Run: `uv run python -m clew.graph.seed && uv run python -m clew.dev --explorers 4 --minutes 5`
