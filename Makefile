# On the hosted VM (deploy/gcp.sh creates .hosted) every target uses the Caddy setup instead of dev ports.
ifneq ($(wildcard .hosted),)
LIVE ?= docker compose -f compose.yaml -f compose.deploy.yaml
else
LIVE ?= docker compose -f compose.yaml -f compose.dev.yaml
endif
API  = $(LIVE) exec api python -m

.PHONY: up up-deploy down seed reset session stop kill-explorer restart-all deploy-v2 rollback mission \
        snapshot-v1 replay score baseline github-labels test test-integration lint docs logs dev fixtures

up:                ## everything for local use (explorers start at 0)
	$(LIVE) up -d --build
up-deploy:         ## hosted: Caddy in front
	docker compose -f compose.yaml -f compose.deploy.yaml up -d --build
down:
	$(LIVE) down
seed:              ## indexes + App + Release v1 into nebula_seed, then copy to the live graph
	$(API) clew.graph.seed
reset:             ## store back to v1 + fresh map
	$(API) clew.cli reset
session:           ## make session N=4 MIN=10 MODE=shared START=fresh|continue|v1_snapshot
	$(API) clew.cli session --explorers $(or $(N),4) --minutes $(or $(MIN),10) --mode $(or $(MODE),shared) --start $(or $(START),fresh)
stop:
	$(API) clew.cli stop
kill-explorer:     ## S2
	$(API) clew.cli kill-explorer
restart-all:       ## S3: restart every Clew service, FalkorDB included
	$(LIVE) restart falkordb mcp api scheduler reporter controller
deploy-v2:         ## S4
	$(API) clew.cli release v2
rollback:
	$(API) clew.cli release v1
mission:           ## make mission STATE='/cart|in|…' TEXT='Test invalid coupon codes'
	$(API) clew.cli mission --state "$(STATE)" --text "$(TEXT)"
snapshot-v1:       ## freeze the current map as <app>_v1_map (CLEW_APP in .env)
	$(API) clew.cli snapshot
replay:            ## make replay BUG=<sig>: replay a bug's steps in a visible browser (local)
	uv run python -m clew.cli replay --bug "$(BUG)" --headed
score:
	uv run python -m scorer.score
baseline:          ## S5: shared vs isolated, 3 sessions each
	uv run python eval/run_baseline.py --runs $(or $(RUNS),3)
github-labels:
	uv run python -m clew.reporter.github --create-labels
dev:               ## no Docker for Clew: store + swarm in local processes (needs a FalkorDB, see README)
	uv run python -m clew.dev --explorers $(or $(N),2) --minutes $(or $(MIN),5)
fixtures:          ## recapture ARIA snapshot fixtures from a running store
	uv run python -m tests.fixtures.capture_snapshots
test:
	uv run pytest -q
test-integration:
	uv run pytest -q -m integration
lint:
	uv run ruff check . && uv run ruff format --check .
docs:
	uv run python -m clew.graph.docs > docs/cypher.md
logs:
	$(LIVE) logs -f --tail=100
