#!/usr/bin/env bash
# Start backend outside Cursor agent sandbox (so macOS File Provider / I/O is not restricted)
set -e
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# free port
if lsof -nP -tiTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -nP -tiTCP:8001 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
  sleep 1
fi
pkill -9 -f 'uvicorn main:app' 2>/dev/null || true

LOG=/tmp/qs-logs/backend-user.log
mkdir -p /tmp/qs-logs
echo "Starting backend at $(date)" | tee "$LOG"
echo "If this sits >90s without 'Application startup complete', free Chrome/RAM and rerun."
exec env -u PYTHONPATH -u PYTHONHOME \
  ./venv/bin/python -u -m uvicorn main:app --host 127.0.0.1 --port 8001 \
  2>&1 | tee -a "$LOG"
