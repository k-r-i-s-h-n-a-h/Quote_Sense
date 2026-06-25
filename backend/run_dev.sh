#!/usr/bin/env bash
# Start QuoteSense backend (FastAPI on port 8001)
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "❌ backend/.env missing — copy .env.example to .env and add your API keys."
  exit 1
fi

if [[ ! -x venv/bin/python ]]; then
  echo "Creating Python virtual environment…"
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
fi

# Free port 8001 if a stale uvicorn from a previous session is still running
if lsof -ti :8001 >/dev/null 2>&1; then
  echo "Stopping stale process on port 8001…"
  lsof -ti :8001 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "Starting backend at http://127.0.0.1:8001"
echo "Health check: http://127.0.0.1:8001/api/health"
exec venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001 --reload
