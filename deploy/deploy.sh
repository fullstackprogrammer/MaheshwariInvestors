#!/usr/bin/env bash
# Redeploy frontend (and optionally backend) to existing EC2.
# Usage:
#   ./deploy/deploy.sh                    # uses deploy/config
#   EC2_IP=54.89.185.96 KEY_PATH=/path/to/key.pem ./deploy/deploy.sh
#   ./deploy/deploy.sh --backend-too       # also sync backend + data and restart API
#
# Requires: Node/npm (frontend build), ssh/scp. Run from repo root.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_TOO=false

for arg in "$@"; do
  case "$arg" in
    --backend-too) BACKEND_TOO=true ;;
  esac
done

# Load config
if [ -f "$SCRIPT_DIR/config" ]; then
  # shellcheck source=/dev/null
  set -a
  source "$SCRIPT_DIR/config"
  set +a
fi
EC2_IP="${EC2_IP:-$EC2_IP}"
KEY_PATH="${KEY_PATH:-$KEY_PATH}"
EC2_USER="${EC2_USER:-ec2-user}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/home/ec2-user/MaheshwariInvestors}"

if [ -z "$EC2_IP" ] || [ -z "$KEY_PATH" ]; then
  echo "Set EC2_IP and KEY_PATH in deploy/config or pass as env vars." >&2
  exit 1
fi

API_URL="http://${EC2_IP}:8000"
echo "Deploying to $EC2_IP (API: $API_URL)"

# 1. Build frontend
cd "$REPO_ROOT/frontend"
export VITE_API_BASE_URL="$API_URL"
npm run build
cd "$REPO_ROOT"

# 2. Upload frontend dist
echo "Uploading frontend dist..."
scp -i "$KEY_PATH" -r "$REPO_ROOT/frontend/dist" "${EC2_USER}@${EC2_IP}:${REMOTE_APP_DIR}/frontend/"

# 3. Optionally sync backend + data
if [ "$BACKEND_TOO" = true ]; then
  echo "Syncing backend and data..."
  scp -i "$KEY_PATH" "$REPO_ROOT/backend/main.py" "$REPO_ROOT/backend/requirements.txt" \
    "$REPO_ROOT/backend/response_cache.py" \
    "$REPO_ROOT/backend/csp_universe.py" "$REPO_ROOT/backend/csp_screener.py" \
    "$REPO_ROOT/backend/csp_math.py" "$REPO_ROOT/backend/csp_cache.py" \
    "$REPO_ROOT/backend/covered_calls_screener.py" \
    "${EC2_USER}@${EC2_IP}:${REMOTE_APP_DIR}/backend/"
  [ -d "$REPO_ROOT/data" ] && scp -i "$KEY_PATH" -r "$REPO_ROOT/data" "${EC2_USER}@${EC2_IP}:${REMOTE_APP_DIR}/"
  [ -f "$REPO_ROOT/DFWInvestors2026StockPicks.csv" ] && scp -i "$KEY_PATH" "$REPO_ROOT/DFWInvestors2026StockPicks.csv" "${EC2_USER}@${EC2_IP}:${REMOTE_APP_DIR}/"
fi

# 4. Reload Nginx (always). Restart backend only if we deployed backend (avoids clearing cache on frontend-only deploy)
echo "Reloading Nginx on EC2..."
if [ "$BACKEND_TOO" = true ]; then
  echo "Restarting backend (backend was updated)..."
  ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${EC2_USER}@${EC2_IP}" \
    "sudo systemctl restart maheshwari-api; sudo systemctl reload nginx; echo Done"
else
  ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${EC2_USER}@${EC2_IP}" \
    "sudo systemctl reload nginx; echo Done"
  echo "Backend not restarted (frontend-only deploy). Cache remains warm."
fi

echo "Deploy done. App: http://${EC2_IP}"
