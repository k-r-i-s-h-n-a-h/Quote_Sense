#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
pip install -q -r backend/requirements.txt
cd backend
echo "Starting API on http://127.0.0.1:8001"
exec uvicorn main:app --host 127.0.0.1 --port 8001 --reload
