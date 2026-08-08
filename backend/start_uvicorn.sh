#!/usr/bin/env bash
# Manual uvicorn with project venv — same behaviour, for people who want
# the classic "source venv && uvicorn" flow, but with the fast path fallback.
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8001}"

echo "Tip: if this freezes with no logs for >60s, press Ctrl+C and run:"
echo "  ./run_dev.sh"
echo "  (uses fast cache venv under /tmp by default)"
echo ""

if [[ ! -x venv/bin/python ]]; then
  echo "❌ ./venv missing"
  exit 1
fi

if lsof -nP -iTCP:"$PORT" >/dev/null 2>&1; then
  echo "Port $PORT busy — killing listeners…"
  lsof -nP -tiTCP:"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# Prefer cache python for actual execution (packages live off Desktop)
# but still work from this folder so main:app imports your code.
PY="./venv/bin/python"
if [[ -x /tmp/quotesense-backend-venv/bin/python ]]; then
  PY="/tmp/quotesense-backend-venv/bin/python"
  echo "Using cache interpreter: $PY"
  echo "(Your code in this folder is loaded as main:app)"
else
  echo "Using project venv interpreter: $PY"
  echo "⚠️  Cold import can take 1–10+ minutes under low RAM."
fi

export PYTHONUNBUFFERED=1
echo "Starting on http://127.0.0.1:${PORT} …"
exec env -u PYTHONPATH -u PYTHONHOME "$PY" -u -m uvicorn main:app \
  --host 127.0.0.1 --port "$PORT" --log-level info
