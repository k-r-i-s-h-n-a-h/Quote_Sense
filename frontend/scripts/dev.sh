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

# #region agent log
DEBUG_LOG="/Users/krishnahonnikhere/Desktop/tatvaops-quotesense/.cursor/debug-da6531.log"
_ts() { echo $(($(date +%s) * 1000)); }
_dbg() {
  local hid="$1" msg="$2" data="$3"
  # Never break startup if .cursor logs are not writable
  { printf '%s\n' "{\"sessionId\":\"da6531\",\"runId\":\"startup\",\"hypothesisId\":\"$hid\",\"location\":\"dev.sh\",\"message\":\"$msg\",\"data\":$data,\"timestamp\":$(_ts)}" >> "$DEBUG_LOG"; } 2>/dev/null || true
}
# #endregion

# Leftover workers from interrupted runs block new starts and hang compilation.
LEFTOVER_NEXT=0
if pgrep -f "$PWD/node_modules/.bin/next" >/dev/null 2>&1; then
  LEFTOVER_NEXT=1
  echo "Stopping leftover Next.js processes…"
  pkill -9 -f "$PWD/node_modules/.bin/next" 2>/dev/null || true
  pkill -9 -f "$PWD/node_modules/next/dist" 2>/dev/null || true
  sleep 1
fi

PORT_BUSY=0
if lsof -ti :3000 >/dev/null 2>&1; then
  PORT_BUSY=1
  echo "Stopping process on port 3000…"
  lsof -ti :3000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# #region agent log
NEXT_EXISTS=0
[[ -d .next ]] && NEXT_EXISTS=1
NEXT_SIZE=$(du -sk .next 2>/dev/null | awk '{print $1}' || echo 0)
DISK_AVAIL=$(df -k . | awk 'NR==2{print $4}')
_dbg "B" "preflight after cleanup" "{\"leftoverNext\":$LEFTOVER_NEXT,\"portBusy\":$PORT_BUSY,\"nextDirExists\":$NEXT_EXISTS,\"nextSizeKb\":${NEXT_SIZE:-0},\"diskAvailKb\":${DISK_AVAIL:-0},\"pwd\":\"$PWD\"}"
# #endregion

# iCloud Desktop can create duplicate package folders ("next 2", "@babel 3").
# Those break/hang Next.js file watching and leave a stuck .next/dev/lock.
DUP_COUNT=$(find node_modules -maxdepth 2 -type d -name '* *' 2>/dev/null | wc -l | tr -d ' ')
if [[ "${DUP_COUNT:-0}" -gt 0 ]]; then
  echo "⚠️  Found $DUP_COUNT iCloud duplicate folders in node_modules — removing them…"
  # #region agent log
  _dbg "F" "removing iCloud duplicates" "{\"duplicatesBefore\":$DUP_COUNT}"
  # #endregion
  find node_modules -maxdepth 2 -type d -name '* *' -print0 2>/dev/null | while IFS= read -r -d '' d; do
    rm -rf "$d"
  done
  # Stale lock from a previous hung start
  rm -f .next/dev/lock 2>/dev/null || true
  echo "✅ Duplicate folders removed."
  # #region agent log
  _dbg "F" "duplicates removed" "{\"duplicatesBefore\":$DUP_COUNT}"
  # #endregion
fi

# #region agent log
# iCloud "dataless" placeholders: Next hangs in getRequestHandlers after "Starting..."
DATALESS_COUNT=$(find node_modules -maxdepth 3 -flags +dataless 2>/dev/null | wc -l | tr -d ' ')
_dbg "H" "iCloud dataless check" "{\"datalessMaxDepth3\":${DATALESS_COUNT:-0}}"
if [[ "${DATALESS_COUNT:-0}" -gt 100 ]]; then
  echo "⚠️  Found $DATALESS_COUNT iCloud dataless files under node_modules (depth≤3)."
  echo "   Next.js will hang at \"Starting…\" until packages are fully local."
  echo "   Fix: rm -rf node_modules .next && npm ci"
fi
# #endregion

# Default to webpack — Turbopack often hangs on iCloud-synced Desktop folders.
# Opt in to Turbopack with: USE_TURBOPACK=1 npm run dev
DEV_FLAGS=(dev --hostname 127.0.0.1 --port 3000)
if [[ "${USE_TURBOPACK:-}" == "1" ]]; then
  echo "Launching Next.js (Turbopack) at http://127.0.0.1:3000 …"
  # #region agent log
  _dbg "A" "launching turbopack" "{\"bundler\":\"turbopack\",\"port\":3000}"
  # #endregion
else
  DEV_FLAGS+=(--webpack)
  echo "Launching Next.js (webpack) at http://127.0.0.1:3000 …"
  echo "  First compile can take 3–5 min on iCloud Desktop — wait for ✓ Ready, then ○ Compiling to finish."
  echo "  Tip: move repo to ~/Projects/ for much faster dev, or use: npm run dev:built"
  # #region agent log
  _dbg "A" "launching webpack" "{\"bundler\":\"webpack\",\"port\":3000,\"watchpackPolling\":\"$WATCHPACK_POLLING\"}"
  # #endregion
fi

# #region agent log
# Watchdog: keep checking until HTTP responds (port-only is not Ready)
(
  PREV=0
  for SEC in 5 15 30 60 90 120 180 240; do
    sleep $((SEC - PREV))
    PREV=$SEC
    LISTEN=0
    lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1 && LISTEN=1
    PROC=0
    pgrep -f "$PWD/node_modules/.bin/next" >/dev/null 2>&1 && PROC=1
    CODE=$(curl -s -o /dev/null -m 2 -w "%{http_code}" http://127.0.0.1:3000/ 2>/dev/null || echo "000")
    HTTP=0
    [[ "$CODE" =~ ^[23] ]] && HTTP=1
    NEXT_SIZE=$(du -sk .next 2>/dev/null | awk '{print $1}' || echo 0)
    _dbg "C" "watchdog tick" "{\"elapsedSec\":$SEC,\"portListening\":$LISTEN,\"nextProcAlive\":$PROC,\"httpOk\":$HTTP,\"httpCode\":\"$CODE\",\"nextSizeKb\":${NEXT_SIZE:-0}}"
    if [[ $HTTP -eq 1 ]]; then
      _dbg "C" "http ready" "{\"elapsedSec\":$SEC,\"httpCode\":\"$CODE\"}"
      break
    fi
  done
) >/dev/null 2>&1 &
# #endregion

# #region agent log
_dbg "D" "pre exec next" "{\"nextBin\":\"$NEXT_BIN\",\"pwd\":\"$PWD\",\"flags\":\"${DEV_FLAGS[*]}\"}"
# #endregion
exec "$NEXT_BIN" "${DEV_FLAGS[@]}"
