#!/usr/bin/env bash
# Compute Engine startup script: Docker, Compose and make (runs once on first boot; safe to re-run).
set -euo pipefail
if ! command -v docker >/dev/null; then
  apt-get update -y && apt-get install -y make git ca-certificates curl
  curl -fsSL https://get.docker.com | sh
fi
