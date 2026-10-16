# Build progress (kept current so anyone can pick up where the last session stopped)

Last updated: 2026-10-17 (Sat), during the Claude Code build session.

## Done

- **M0/M1 (committed):** store (v1/v2, bugs, decoys, hooks), query library Q01–Q55 with tests (V1 on 4.18.3 and 4.22.1), fingerprint and extraction on 54 real snapshots (V2), explorer worker, oracles, deterministic and Gemini page reader.
- **M2 (in progress):** MCP server (`clew/mcp_server`), audited tools, GitHub client (dry run by default), Reporter runner (deterministic writer + ADK path), release watcher, importance, regression pipeline, `clew/dev.py` all-in-one runner.
  - Verified locally: 4 explorers + reporter + watcher find, confirm in a fresh session and file B1, B2, B3 within ~70 s and B4 (variation mode) at ~3.5 min; Q32 duplicates = 0; no decoys filed.
  - S4 verified locally: deploy v2 → 203 replay jobs + 4 verify_fix jobs; B2 verified fixed; B1/B3/B4 still present; "Add to bag" healed (rename Fact); Gift cards link added to every known page; R1 flagged as a regression.

## Next (in order)

1. ~~Integration test~~ done: `uv run pytest -m integration` (one explorer, ~6.5 min).
2. API (FastAPI, SSE, sessions, missions, Show Cypher), controller (Docker kill/scale), `clew/cli.py`.
3. Dockerfiles, `compose*.yaml`, Caddyfile, Makefile.
4. War-room UI (Vite + React + Cytoscape).
5. Scorer, S5 baseline script, README, `docs/graph-model.md`, `make docs`.

## Needs a human

- Gemini credentials (V7, V8): set `LLM_BACKEND=vertex` + project, or `gemini_api` + key. Until then everything runs on the deterministic reader and writer.
- GitHub token for real issues (V11): fine-grained, Issues on the issues repo only; `make github-labels`.
- GCP VM deploy (§21), demo video, blog, submission form, Discord questions (V14).

## Dev setup used in this session

- Store: `SHOP_DB=artifacts/dev.db SHOP_ADMIN_TOKEN=devtoken SHOP_EXPLORER_PASSWORD=pw uv run uvicorn shop.app:app --port 8090`
- FalkorDB: `docker run -d --name clew-falkordb-dev -p 127.0.0.1:6390:6379 falkordb/falkordb:v4.22.1`
- Env: `source artifacts/dev.env` (FALKORDB_PORT=6390, CLEW_GRAPH=nebula_dev, LLM_BACKEND=off)
- Run: `uv run python -m clew.graph.seed && uv run python -m clew.dev --explorers 4 --minutes 5`
