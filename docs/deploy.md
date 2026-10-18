# Deploying Clew (Google Cloud, one VM)

The whole system runs on one Compute Engine `e2-standard-4` (4 vCPU, 16 GB): FalkorDB, the store, API+UI, MCP, scheduler, reporter, controller and up to 4 explorer containers. Only Caddy is public (80/443, automatic HTTPS). FalkorDB, MCP, the controller and the store's `/__*` hooks are never routed.

## What you need

- A Google Cloud project with billing (and the hackathon credits).
- The `gcloud` CLI on your laptop: `brew install --cask google-cloud-sdk`, then `gcloud auth login`.
- Optional: a domain. Without one, the script uses `<ip>.sslip.io`, which resolves to the VM's IP, so Caddy still gets a real HTTPS certificate.

## LLM on the hosted VM

LM Studio runs on your laptop, not on the VM. On the VM choose:

- `LLM=vertex`: Gemini through Vertex AI, authenticated by the VM's service account (no keys). The script grants it `roles/aiplatform.user`. Confirm the Gemini model IDs in `config/models.yaml` (`gemini:` profile) exist in your project's Model Garden. If a call fails, the page reader falls back to its deterministic defaults and the Reporter to its template writer, so the demo keeps working.
- `LLM=off`: the deterministic page reader and template Reporter. No model, fastest, free.

## Steps

```bash
cd /path/to/clew
export PROJECT_ID=your-gcp-project      # REGION/ZONE default to asia-south1 / asia-south1-a
export LLM=vertex                       # or off

deploy/gcp.sh create    # enables APIs, service account, static IP, firewall (80/443 + IAP SSH), VM with Docker
                        # wait ~2 minutes for Docker to install on first boot
deploy/gcp.sh push      # uploads HEAD (git archive) + a hosted .env with fresh secrets; builds, starts, seeds
                        # prints: Clew is up: https://<ip>.sslip.io
deploy/gcp.sh status    # containers and URL
deploy/gcp.sh logs      # follow logs
deploy/gcp.sh ssh       # a shell on the VM (then: cd ~/clew && sudo make session N=4 MIN=10, etc.)
```

To redeploy after a code change: commit, then `deploy/gcp.sh push`. The VM's `.env` is kept; only the code is replaced.

The hosted `.env` (from `deploy/make-env.sh`) sets:

- `HOSTED_MODE=true`: at most 4 explorers and 10 minutes per session, one session at a time, a daily cap, no "Restart all";
- `GITHUB_FILING=dry_run`: issues appear in the war room only;
- `CLEW_DOMAIN`: the domain Caddy serves.

To file real GitHub issues from the VM, set `GITHUB_FILING=on`, `GITHUB_REPO` and `GITHUB_TOKEN` (fine-grained, Issues on that repo only) in `~/clew/.env` on the VM, then `sudo make up-deploy`.

## Cost and teardown

- `e2-standard-4` is about $0.13–0.17/hour, so a few days of hosting is a few dollars. Gemini Flash calls for a session cost cents.
- Set a budget alert (Billing → Budgets & alerts).
- After judging: `deploy/gcp.sh destroy` deletes the VM, the static IP and the firewall rules.

## Checklist before sharing the URL

- [ ] `https://<domain>` loads the war room, and the header shows the release and "no session running".
- [ ] Start a session from the header (4 · 10 · fresh map); pages appear within a minute.
- [ ] `https://<domain>/__version` returns 404 (Caddy blocks the hooks).
- [ ] Ports 6379, 8000 and 8003 are not reachable from outside (only 80/443 are open).
