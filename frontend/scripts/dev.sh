#!/usr/bin/env bash
# Free port 3000 then start Next.js (safe to run even if nothing is listening)
set -e
cd "$(dirname "$0")/.."

NEXT_BIN="./node_modules/.bin/next"
if [[ ! -x "$NEXT_BIN" ]]; then
  echo "❌ Next.js not installed. Run: npm ci"
  exit 1
fi

echo "Starting QuoteSense frontend (Next.js)…"

# Leftover workers from interrupted runs block new starts and hang compilation.
if pgrep -f "$PWD/node_modules/.bin/next" >/dev/null 2>&1; then
  echo "Stopping leftover Next.js processes…"
  pkill -9 -f "$PWD/node_modules/.bin/next" 2>/dev/null || true
  pkill -9 -f "$PWD/node_modules/next/dist" 2>/dev/null || true
  sleep 1
fi

if lsof -ti :3000 >/dev/null 2>&1; then
  echo "Stopping process on port 3000…"
  lsof -ti :3000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# Stale dev lock/cache from Ctrl+C causes silent hangs on restart.
rm -rf .next/dev

# Turbopack is ~100x faster locally; use dev:webpack if you hit Turbopack issues.
DEV_FLAGS=(dev --hostname 127.0.0.1 --port 3000)
if [[ "${USE_WEBPACK:-}" == "1" ]]; then
  DEV_FLAGS+=(--webpack)
  echo "Launching Next.js (webpack) at http://127.0.0.1:3000 …"
else
  echo "Launching Next.js (Turbopack) at http://127.0.0.1:3000 …"
fi

exec "$NEXT_BIN" "${DEV_FLAGS[@]}"
