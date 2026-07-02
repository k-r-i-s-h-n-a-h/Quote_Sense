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

# iCloud Desktop: native file watchers hang; polling keeps dev compilations moving.
export WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}"
export WATCHPACK_POLLING_INTERVAL="${WATCHPACK_POLLING_INTERVAL:-2000}"
export CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-true}"

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

DEBUG_LOG="/Users/krishnahonnikhere/Desktop/tatvaops-quotesense/.cursor/debug-b7c34a.log"
_ts() { echo $(($(date +%s) * 1000)); }
_dbg() {
  local hid="$1" msg="$2" data="$3"
  printf '%s\n' "{\"sessionId\":\"b7c34a\",\"hypothesisId\":\"$hid\",\"location\":\"dev.sh\",\"message\":\"$msg\",\"data\":$data,\"timestamp\":$(_ts)}" >> "$DEBUG_LOG"
}

# Default to webpack — Turbopack often hangs on iCloud-synced Desktop folders.
# Opt in to Turbopack with: USE_TURBOPACK=1 npm run dev
DEV_FLAGS=(dev --hostname 127.0.0.1 --port 3000)
if [[ "${USE_TURBOPACK:-}" == "1" ]]; then
  echo "Launching Next.js (Turbopack) at http://127.0.0.1:3000 …"
  _dbg "H1" "launching turbopack" "{\"bundler\":\"turbopack\",\"port\":3000}"
else
  DEV_FLAGS+=(--webpack)
  echo "Launching Next.js (webpack) at http://127.0.0.1:3000 …"
  echo "  First compile can take 3–5 min on iCloud Desktop — wait for ✓ Ready, then ○ Compiling to finish."
  echo "  Tip: move repo to ~/Projects/ for much faster dev, or use: npm run dev:built"
  _dbg "H1" "launching webpack" "{\"bundler\":\"webpack\",\"port\":3000}"
fi

_dbg "H5" "pre exec next" "{\"nextBin\":\"$NEXT_BIN\",\"pwd\":\"$PWD\"}"
exec "$NEXT_BIN" "${DEV_FLAGS[@]}"
