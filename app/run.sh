#!/bin/sh
# The hackathon pod runs this, and again when it stops. Serves on $PORT; requests keep the /hackathon prefix
# ($ROOT_PATH, handled in app.py). --reload restarts the server when a .py file in app/ changes.
# On your own machine: uv run uvicorn app:app --reload (then open http://127.0.0.1:8000/).
set -e
cd "$(dirname "$0")"
uv sync --quiet
exec uv run uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --reload --reload-dir .
