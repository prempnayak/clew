# Decisions and verified facts

One dated line per verified fact or design change. When the plan (`docs/handoff.md`) and reality disagree, reality wins and is written down here.

## 2026-10-17

### Verify-first results (handoff §26)

- **V1 ✅** All query tests (`tests/unit/test_queries.py`) pass on embedded FalkorDB 4.18.3 (`falkordblite` 0.10.0) **and** on the Docker image `falkordb/falkordb:v4.22.1`, the newest stable tag on Oct 17. We pin `v4.22.1` in `.env.example` and Compose.
- **V2 ✅** The fingerprint equivalence table (§10.2) holds on 54 real snapshots of every store page (v1 and v2, logged in and out): `tests/unit/test_fingerprint.py`. The 54 fixtures collapse to 21 states. One full v1 exploration made 24 states (target ~20; 50+ would mean content leaking into the hash). The rules in `config/fingerprint.yaml` are the handoff's, plus `strong, emphasis, code, separator, figure, time` added to the ignored roles.
- **V4 ✅** Every store form field and button has an accessible name in the ARIA snapshot (`<label for>` and visible button text). Empty lists render as `- list "Name"` with no colon, so they tokenize as `list:empty`.
- **V5 (partial) ✅** Playwright's `pageerror` gives `error.name` = `TypeError` and `error.message` without the name, so the observer records `f"{name}: {message}"`. An uncaught error inside an XHR `onload` callback reaches `pageerror`. One explorer with the deterministic reader found B1, B2 and B3 in about 90 s.
- **V6 ✅ (local)** `networkidle` settles on every store page. `perform.settle` waits 150 ms, then for `load` and `networkidle`, each capped at 5 s, so a click that starts a navigation is not missed.

### Changes to the plan

- **Fresh browser context for every work item.** Each explorer starts every claimed item in a new logged-out context at the entry page and walks the shortest known route from there. Long-lived contexts leak hidden state (the cart's contents) into `LEADS_TO` edges: in one explorer "Cart" leads to *Cart (with items)*, in a fresh one to *Cart (empty)*. Routes would then drift and repro steps would be wrong. Routes in the store are 1–6 steps, so the cost is about 1–2 s per item.
- **Carts and wishlists belong to the browser session** in Nebula Gear, not to the user (handoff Appendix A suggested per-account carts). Logging in keeps the session's cart. With fresh contexts, every route starts from an empty cart, so outcomes are deterministic. Explorers still log in with their own accounts.
- **No quantity field on the product page.** It would turn "Add to cart" into a form with input cases, triple the product page's actions and complicate the v2 rename. Recorded here because Appendix A.1 lists a quantity.
- **The store shows a promo banner ("use code SAVE10").** The deterministic page reader offers code-like strings printed on the page (`page_code_pattern` in `config/inputs.yaml`) as the valid value of code fields, and Facts learned later feed the same list. That is how a tester without an LLM finds a valid coupon, without any code knowing it.
- **The store exposes its release in `<meta name="app-release">`.** An explorer only records outcomes when the release the page shows equals the graph's current release (Q37). Without this check, explorers would record v2 behaviour as v1 edges in the seconds between a deploy and the release watcher noticing it, and the v1 baseline would be overwritten.
- **Rule signatures leave out the auth part:** `rule|<rule id>|<route>|<hash8>`. The same cart seen logged in and logged out has the same structure, and B1 showed up as two bugs before this change.
- **Regression signatures leave out the auth part too:** `regression|<route>|<hash8>#<role:target>`. R1 broke the same button on the logged-out and logged-in search pages and was filed twice before this change. Both actions become triggers of one bug, and both are marked broken.
- **Orders belong to the browser session** (shown as "Recent orders" on the account page), for the same reason as carts: the account page's structure changed with each account's order history, so routes to it drifted between explorers.
- **Routes re-plan once on drift** from wherever the step landed to the same destination, before giving up.
- **Problems seen during replay jobs are `suspect`s.** Replays exist to diff releases; the regression pipeline (Q19) decides what changed and files one `regression` bug. Otherwise R1 would be filed twice (as a regression and as a `pageerror`).
- **Q19 is stricter than the handoff's draft.** An action counts as regressed only when none of its new-release outcomes is a working edge to a page it reached before, and actions that already failed somewhere in the previous release are skipped. An action's outcome can depend on hidden state (logging in from the checkout redirect with an empty cart gave a 500 in v1 and a redirect in v2), and the draft flagged that fix as a regression.
- **Q11 has a second branch for triggers on the entry page.** `algo.SPpaths` yields nothing when source = target, so a bug triggered on the entry page (B4: "Open product" on Home, the 8th product) had no repro steps. Found by `test_route_to_self_and_repro_on_entry`.
- **Q36 returns `same_trigger`** (`size((b)-[:TRIGGERED_BY]->(oa)) > 0`); a bare pattern in `RETURN` returns paths on FalkorDB.
- **Q10 and Q11 also return the states along the path,** so the explorer can check for drift after each step. Q10b returns the action's state, role, name and aliases. Q06 returns the action's origin and next instance. Q15b stores the issue title and body (the UI shows dry-run issues). Q34a/Q34b store minutes, start map and summary.
- **Page-reader schema uses a list of `{field_id, value}` pairs** instead of `dict[str, str]`: Gemini's response schema does not support free-form maps well.
- **Extra read queries Q37–Q55** for the API, the UI and the scorer (current release, bug detail, pending jobs, entry state, counters, state detail, agents, tool calls, jobs, sessions, map nodes, action outcomes, previous release, missions, session stats, route patterns, map growth, release changes, timeline). They follow the same rules: one file each, parameterized, with headers and tests.
- **`clew/common/log.py`** instead of `logging.py`, so the module never shadows the standard library.
- **Dev ports.** A sibling project (Causeway) uses 6379, 3000, 8000 and 8081 on the team laptop, so local development runs FalkorDB on 6390. Compose files keep the standard ports inside the Compose network.

## 2026-10-17 (afternoon)

- **V3 ✅** `mcr.microsoft.com/playwright/python:v1.63.0-noble` exists (no 1.64 image yet), so `playwright==1.63.0` is pinned on both sides; Chromium runs in the container with `ipc: host` and `init: true`.
- **V12 ✅ with a change.** The controller scales explorer containers per session. `docker kill` counts as a manual stop, so the `unless-stopped` restart policy does **not** bring the container back (exit 137, 0 restarts). The controller now starts the killed container again after 5 s; the new process takes a new agent name from the Redis counter. S2 measured in Docker: explorer-1 killed holding a claim at 06:51:34; explorer-5 claimed the same action at 06:53:34 (lease 120 s); the container rejoined as explorer-6.
- **V13 ✅** FalkorDB 4.22 keeps its data in `/var/lib/falkordb/data` (not `/data`); the volume mounts there. `make restart-all` restarted FalkorDB mid-session and the map, bugs and running session survived (AOF). The explorers' clients reconnected on their own.
- **V9/V10 (partial) ✅** MCP over streamable HTTP with bearer-token middleware works (`tests/spikes/test_mcp_http.py`); the ADK Reporter calls the tools through `McpToolset` in Docker. The Gemini half of V7–V9 still needs credentials.
- **LLM backend `openai`** (any OpenAI-compatible server) added beside Gemini, for development on LM Studio with Qwen3-8B (4-bit). Model IDs per backend live in `config/models.yaml`. The ADK Reporter and Strategist use ADK's LiteLLM adapter for this backend, so the agent code path is the same as with Gemini.
- **The page reader's answer is merged with the deterministic defaults.** The model's choices win, but candidates it does not mention keep their default cases (a skip must be explicit), and the action kind always comes from extraction. A small model otherwise drops parts of the page or mislabels a form as a click. The model is also given the structural name as a suggestion, and facts that echo its context are dropped: Qwen copied the example name ("Cart (coupon applied)") onto every cart page.
- **The Reporter's turn must end with the expected tool call, or the template writer finishes the claim.** Qwen3-8B sometimes stops after reading (`get_bug`, `repro_steps`, `affected_pages`) without calling `file_issue`. The turn's message now names the closing call, and if Q29c still shows no successful call, the deterministic writer files through the same audited tools within the same claim. The ADK instruction is passed as a callable, because ADK would otherwise read `{agent}`, `{run}` in the issue template as session-state keys.
- **S1 in Docker with Qwen3-8B on LM Studio, 4 explorers, 10 minutes (session S-1):** recall 4/4 (B3 39.5 s, B1 67.6 s, B4 141.8 s, B2 367.3 s to first sighting), 0 decoys, 0 duplicate executions, route coverage 11/12 (`/order/:id` not reached). Page reads take 3–18 s each on the local model and LM Studio serves one request at a time, which is why B2 took longer than in deterministic runs.
- **S3 in Docker (session S-2, `START=continue`):** the mission "Test invalid coupon codes" added 4 cases on *Your cart (with items)*. Four explorers claimed them in the same second and finished within 5 s, with no page reads on the way. New fact: "Coupon code = 'save10' → 'Unknown coupon code.'".
- **Transitions keep the route that produced them (`LEADS_TO.via`), and replays walk that route first.** The first Docker S4 run confirmed two false regressions on *Log in (next)*. In v1 an explorer had reached that page from a cart with items; the replay reached it from an empty cart, so "Cart" and "Log in" led elsewhere. The page structure is identical in both cases, so the fingerprint can't tell them apart. With the original route replayed, the second S4 run found only R1. Q07 stores `via` (actions and states from the entry page); Q48 returns it.
- **S4 in Docker with Qwen3-8B (session S-2 on the fresh S1 map):**
  - 188 replay and 4 verify_fix jobs were queued;
  - R1 was detected 2 min 44 s after the deploy, filed as one issue (#5), with the logged-out and logged-in variants merged;
  - the rename was healed;
  - B2 was verified fixed and its issue closed;
  - B1, B3 and B4 got "still present";
  - Gift cards and the notice page were discovered;
  - no other regressions.
  
  Qwen called `file_issue` with a truncated signature; the tool refused it and the template writer filed it.
- **CI runs every test against the pinned FalkorDB image, not the embedded build.** The CI run failed for two reasons, both reproduced in a Linux container:
  1. `ruff format --check` flagged a test appended after formatting.
  2. `falkordblite`'s bundled graph module does not load on Linux (`falkordb.so: not a dynamic executable`), so all 25 graph-backed tests errored at server start.
  
  CI now sets `FALKORDB_EMBEDDED=0` and points the suite at the `falkordb/falkordb:v4.22.1` service; 94 tests pass that way on Linux. `falkordblite` stays the default for local runs on macOS.
