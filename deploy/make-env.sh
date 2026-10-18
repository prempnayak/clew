#!/usr/bin/env bash
# Print a hosted .env: fresh random secrets, hosted caps, dry-run filing. Usage: make-env.sh <domain> <llm> <project>
set -euo pipefail
DOMAIN="$1"; LLM="$2"; PROJECT="$3"
rnd() { openssl rand -hex 16; }
sed -e "s|^FALKORDB_PASSWORD=.*|FALKORDB_PASSWORD=$(rnd)|" \
    -e "s|^SHOP_ADMIN_TOKEN=.*|SHOP_ADMIN_TOKEN=$(rnd)|" \
    -e "s|^SHOP_EXPLORER_PASSWORD=.*|SHOP_EXPLORER_PASSWORD=$(rnd)|" \
    -e "s|^MCP_TOKEN_REPORTER=.*|MCP_TOKEN_REPORTER=$(rnd)|" \
    -e "s|^MCP_TOKEN_STRATEGIST=.*|MCP_TOKEN_STRATEGIST=$(rnd)|" \
    -e "s|^CONTROLLER_TOKEN=.*|CONTROLLER_TOKEN=$(rnd)|" \
    -e "s|^LLM_BACKEND=.*|LLM_BACKEND=${LLM}|" \
    -e "s|^GOOGLE_CLOUD_PROJECT=.*|GOOGLE_CLOUD_PROJECT=${PROJECT}|" \
    -e "s|^GITHUB_FILING=.*|GITHUB_FILING=dry_run|" \
    -e "s|^HOSTED_MODE=.*|HOSTED_MODE=true|" \
    -e "s|^CLEW_DOMAIN=.*|CLEW_DOMAIN=${DOMAIN}|" \
    -e "s|^CLEW_STORE_PUBLIC_URL=.*|CLEW_STORE_PUBLIC_URL=https://shop.${DOMAIN}|" \
    -e "s|  *#.*$||" .env.example
