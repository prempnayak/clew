# Build progress (kept current so anyone can pick up where the last session stopped)

Last updated: 2026-10-17 (Sat) afternoon.

## Done (committed and pushed to origin/main)

- **M0–M3:**
  - store (v1/v2, bugs, decoys, hooks);
  - query library (69 files) with tests: V1 on 4.18.3 and 4.22.1;
  - fingerprint (V2), explorer, oracles, page reader;
  - MCP server, Reporter, watcher, regression pipeline;
  - API, UI, controller, CLI, Docker, Compose, Caddy, Makefile.
- **Local LLM backend** (`LLM_BACKEND=openai`, LM Studio + Qwen3-8B) for the page reader, locate and the ADK agents (via LiteLLM).
- **Scorer** (`make score`), **S5 script** (`make baseline`), **Strategist** (Compose profile `strategist`), **CI** workflow, **README**, `docs/graph-model.md`, `docs/demo-script.md`.
- **Verified in Docker with the local LLM:**
  - S1 twice: 4/4 recall, 0 decoys, 0 duplicates;
  - S2: lease handover at exactly 120 s, killed container rejoins;
  - S3: restart-all keeps the map; mission done with 0 page reads;
  - S4: R1 filed 2 min 44 s after the deploy; rename healed; B2 fixed and closed; no false regressions, after replays walk the original route.

- **S5 measured** (`eval/results/baseline.md`, README table): with the shared map, 215 unique actions vs 93, 0 duplicated actions vs 93, 27 page reads vs 84, and bugs found about 3× faster; B4 was found only with the shared map.
- **CI fixed:** all tests run against the FalkorDB service image (the embedded build doesn't load on Linux).

## Development status

All code work that doesn't need a human is done (Oct 18):

- fixes from the blind test are in (variant diff, sibling heal, default-instance edges, per-form regressions, claim renewal);
- the full S1→S4 rehearsal passed in Docker with Qwen3-8B (README);
- deploy scripts are in `deploy/` (guide: `docs/deploy.md`); demo runbook in `docs/demo-script.md`.

## Needs a human

- **Gemini** (V7, V8): set `LLM_BACKEND=vertex` with `GOOGLE_CLOUD_PROJECT`, or `gemini_api` with `GOOGLE_API_KEY`. Confirm the model IDs in `config/models.yaml` (gemini profile) exist in the Model Garden.
- **GitHub** (V11): a fine-grained token with Issues read/write on the issues repo; set `GITHUB_FILING=on`, `GITHUB_REPO`, `GITHUB_TOKEN`; run `make github-labels`.
- **Hosted VM**: install `gcloud`, `gcloud auth login`, then `deploy/gcp.sh create` and `deploy/gcp.sh push` (`docs/deploy.md`).
- **Submission:** demo video (`docs/demo-script.md`), blog post, submission form with both tracks; ask Discord about the video length and two-track prizes (V14).

## Dev setup used in this session

- Docker stack: `.env` uses host ports 6391 (FalkorDB), 3001 (Browser), 8095 (store), 8010 (MCP), 8082 (UI/API), because Causeway uses the defaults on this laptop.
- LM Studio on the host at :1234; containers reach it at `http://host.docker.internal:1234/v1`.
- No-Docker loop: `source artifacts/dev.env` (FalkorDB on 6390, store on 8090), then `uv run python -m clew.dev --explorers 4 --minutes 5`.
