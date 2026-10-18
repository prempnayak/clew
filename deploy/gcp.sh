#!/usr/bin/env bash
# Deploy Clew to one Compute Engine VM behind Caddy. Run from the repo root on your laptop.
#
#   export PROJECT_ID=your-project            # required
#   export LLM=vertex                          # vertex (Gemini via the VM's service account) or off
#   deploy/gcp.sh create     # APIs, service account, static IP, firewall, VM with Docker
#   deploy/gcp.sh push       # upload the code (git archive of HEAD) and a hosted .env, start everything, and
#                            # reset everything: graph database wiped, store back to v1, a fresh empty map
#   deploy/gcp.sh db         # open the FalkorDB Browser through an SSH tunnel: http://localhost:3001
#   deploy/gcp.sh status     # containers and the public URL
#   deploy/gcp.sh logs       # follow the logs
#   deploy/gcp.sh ssh        # a shell on the VM
#   deploy/gcp.sh destroy    # delete the VM, IP and firewall rules (after judging)
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
ZONE="${ZONE:-asia-south1-a}"
VM="${VM:-clew}"
LLM="${LLM:-vertex}"
SA="clew-vm@${PROJECT_ID}.iam.gserviceaccount.com"
G="gcloud --project=${PROJECT_ID}"

ip() { $G compute addresses describe clew-ip --region="$REGION" --format='value(address)'; }
onvm() { $G compute ssh "$VM" --zone="$ZONE" --tunnel-through-iap --command="$1"; }

case "${1:-}" in
create)
  $G services enable compute.googleapis.com aiplatform.googleapis.com iap.googleapis.com
  $G iam service-accounts describe "$SA" >/dev/null 2>&1 ||
    $G iam service-accounts create clew-vm --display-name="Clew VM"
  $G projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="roles/aiplatform.user" --condition=None >/dev/null
  $G compute addresses describe clew-ip --region="$REGION" >/dev/null 2>&1 ||
    $G compute addresses create clew-ip --region="$REGION"
  $G compute firewall-rules describe clew-web >/dev/null 2>&1 ||
    $G compute firewall-rules create clew-web --allow=tcp:80,tcp:443 --target-tags=clew-web
  $G compute firewall-rules describe clew-iap-ssh >/dev/null 2>&1 ||
    $G compute firewall-rules create clew-iap-ssh --allow=tcp:22 --source-ranges=35.235.240.0/20 \
      --target-tags=clew-ssh
  $G compute instances describe "$VM" --zone="$ZONE" >/dev/null 2>&1 ||
    $G compute instances create "$VM" --zone="$ZONE" --machine-type=e2-standard-4 \
      --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud --boot-disk-size=40GB \
      --address="$(ip)" --service-account="$SA" --scopes=cloud-platform --tags=clew-web,clew-ssh \
      --metadata-from-file=startup-script=deploy/vm-setup.sh
  echo "VM created. Public IP: $(ip). Docker installs on first boot (about 2 minutes); then run: deploy/gcp.sh push"
  ;;
push)
  IP="$(ip)"
  DOMAIN="${CLEW_DOMAIN:-${IP}.sslip.io}"          # sslip.io resolves to the IP, so Caddy can get a certificate
  deploy/make-env.sh "$DOMAIN" "$LLM" "$PROJECT_ID" > /tmp/clew.env.hosted
  git archive --format=tar.gz -o /tmp/clew.tgz HEAD
  $G compute scp /tmp/clew.tgz /tmp/clew.env.hosted "$VM":/tmp/ --zone="$ZONE" --tunnel-through-iap
  rm -f /tmp/clew.env.hosted
  onvm "set -e; mkdir -p ~/clew && tar -xzf /tmp/clew.tgz -C ~/clew && \
        if [ ! -f ~/clew/.env ]; then mv /tmp/clew.env.hosted ~/clew/.env; else rm -f /tmp/clew.env.hosted; fi && \
        sudo docker ps -aq --filter label=clew.role=explorer | xargs -r sudo docker rm -f && \
        cd ~/clew && touch .hosted && sudo make up-deploy && \
        C='sudo docker compose -f compose.yaml -f compose.deploy.yaml' && \
        \$C exec -T falkordb sh -c 'redis-cli -a \"\$FALKORDB_PASSWORD\" --no-auth-warning FLUSHALL' && \
        \$C exec -T api sh -c 'rm -rf /data/screenshots/*' && \
        \$C exec -T api python -m clew.cli reset"
  echo "Clew is up: https://${DOMAIN}   (the store: https://shop.${DOMAIN})"
  ;;
status)
  onvm "cd ~/clew && sudo docker compose -f compose.yaml -f compose.deploy.yaml ps"
  echo "URL: https://$(ip).sslip.io (or your CLEW_DOMAIN)"
  ;;
logs) onvm "cd ~/clew && sudo docker compose -f compose.yaml -f compose.deploy.yaml logs -f --tail=100" ;;
db)
  # The FalkorDB Browser listens only on the VM's localhost; tunnel it to this laptop (nothing is public).
  PW="$(onvm "grep '^FALKORDB_PASSWORD=' ~/clew/.env | cut -d= -f2-" 2>/dev/null | tail -1)"
  echo "FalkorDB Browser: http://localhost:${DB_PORT:-3001}"
  echo "  connect with host: localhost   port: 6379   username: (empty)   password: ${PW}"
  echo "  graph: nebula_live        (Ctrl+C closes the tunnel)"
  $G compute ssh "$VM" --zone="$ZONE" --tunnel-through-iap -- -N -L "${DB_PORT:-3001}:localhost:3000"
  ;;
ssh) $G compute ssh "$VM" --zone="$ZONE" --tunnel-through-iap ;;
destroy)
  $G compute instances delete "$VM" --zone="$ZONE" --quiet || true
  $G compute addresses delete clew-ip --region="$REGION" --quiet || true
  $G compute firewall-rules delete clew-web clew-iap-ssh --quiet || true
  ;;
*) sed -n '2,13p' "$0"; exit 1 ;;
esac
