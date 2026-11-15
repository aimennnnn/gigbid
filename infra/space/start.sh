#!/bin/bash
# One container: the API on 127.0.0.1:8000 (not reachable from outside), the web app on $PORT (default 7860).
# The web app forwards /api/* to the API.
set -e
mkdir -p "${GIGBID_STATE_DIR:-/tmp/gigbid-state}"
uv run --no-sync uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
# wait until the API answers, so the first page a visitor opens can sign in
for i in $(seq 60); do (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null && break; sleep 1; done
cd apps/web
exec npx next start --hostname 0.0.0.0 --port "${PORT:-7860}"
