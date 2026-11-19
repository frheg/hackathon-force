#!/bin/sh
# Pod/local entry. ROLE=backend (API) | ui (static + /api proxy) | worker (GPU jobs). Ports 8460/8461/8462 (8300/8301 are taken on kratos).
cd "$(dirname "$0")/backend" || exit 1
case "${ROLE:-backend}" in
  backend) exec uv run uvicorn se.api.main:app --host 0.0.0.0 --port "${PORT:-8460}" ;;
  ui)      exec env BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8460}" PORT="${PORT:-8461}" uv run python ../ui/serve.py ;;
  worker)  exec uv run --extra gpu uvicorn se.api.worker:app --host 0.0.0.0 --port "${PORT:-8462}" ;;
  *) echo "ROLE must be backend, ui or worker" >&2; exit 2 ;;
esac
