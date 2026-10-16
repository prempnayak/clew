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
- **Problems seen during replay jobs are `suspect`s.** Replays exist to diff releases; the regression pipeline (Q19) decides what changed and files one `regression` bug. Otherwise R1 would be filed twice (as a regression and as a `pageerror`).
- **Q19 is stricter than the handoff's draft.** An action counts as regressed only when none of its new-release outcomes is a working edge to a page it reached before, and actions that already failed somewhere in the previous release are skipped. An action's outcome can depend on hidden state (logging in from the checkout redirect with an empty cart gave a 500 in v1 and a redirect in v2), and the draft flagged that fix as a regression.
- **Q11 has a second branch for triggers on the entry page.** `algo.SPpaths` yields nothing when source = target, so a bug triggered on the entry page (B4: "Open product" on Home, the 8th product) had no repro steps. Found by `test_route_to_self_and_repro_on_entry`.
- **Q36 returns `same_trigger`** (`size((b)-[:TRIGGERED_BY]->(oa)) > 0`); a bare pattern in `RETURN` returns paths on FalkorDB.
- **Q10 and Q11 also return the states along the path,** so the explorer can check for drift after each step. Q10b returns the action's state, role, name and aliases. Q06 returns the action's origin and next instance. Q15b stores the issue title and body (the UI shows dry-run issues). Q34a/Q34b store minutes, start map and summary.
- **Page-reader schema uses a list of `{field_id, value}` pairs** instead of `dict[str, str]`: Gemini's response schema does not support free-form maps well.
- **Extra read queries Q37–Q55** for the API, the UI and the scorer (current release, bug detail, pending jobs, entry state, counters, state detail, agents, tool calls, jobs, sessions, map nodes, action outcomes, previous release, missions, session stats, route patterns, map growth, release changes, timeline). They follow the same rules: one file each, parameterized, with headers and tests.
- **`clew/common/log.py`** instead of `logging.py`, so the module never shadows the standard library.
- **Dev ports.** A sibling project (Causeway) uses 6379, 3000, 8000 and 8081 on the team laptop, so local development runs FalkorDB on 6390. Compose files keep the standard ports inside the Compose network.
