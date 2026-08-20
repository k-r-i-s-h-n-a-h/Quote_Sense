#!/usr/bin/env bash
# Start QuoteSense frontend.
# Desktop/iCloud often leaves node_modules "dataless" → Next hangs at Starting…
# We install deps under /tmp and symlink node_modules there (fast, local disk).
set -e
cd "$(dirname "$0")"

export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://127.0.0.1:8001}"
export WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}"
export CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-true}"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"

TMP_APP="/tmp/qs-frontend-app"
TMP_NM="$TMP_APP/node_modules"

# Ensure off-Desktop node_modules (avoids 6000+ iCloud placeholder hangs).
# Also detect a broken Next install (bin exists but server files were purged from /tmp).
if [[ ! -x "$TMP_NM/.bin/next" || ! -f "$TMP_NM/next/dist/server/require-hook.js" ]]; then
  echo "Installing frontend deps under $TMP_APP (local disk, not iCloud)…"
  mkdir -p "$TMP_APP"
  cp package.json "$TMP_APP/"
  [[ -f package-lock.json ]] && cp package-lock.json "$TMP_APP/"
  # Partial /tmp installs cause: Cannot find module '../server/require-hook'
  rm -rf "$TMP_NM"
  (cd "$TMP_APP" && npm install --no-fund --no-audit)
fi

if [[ -d node_modules && ! -L node_modules ]]; then
  echo "Replacing Desktop node_modules with symlink to $TMP_NM …"
  # keep one backup once; ignore if exists
  if [[ ! -e node_modules.icloud-broken ]]; then
    mv node_modules node_modules.icloud-broken
  else
    rm -rf node_modules
  fi
fi
if [[ ! -L node_modules ]]; then
  ln -sfn "$TMP_NM" node_modules
fi

# free port 3000
if lsof -nP -iTCP:3000 >/dev/null 2>&1; then
  echo "Stopping process on :3000…"
  lsof -nP -tiTCP:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
  sleep 1
fi
pkill -9 -f "$PWD/node_modules/.bin/next" 2>/dev/null || true
rm -rf .next/dev/lock .next/cache 2>/dev/null || true

echo "============================================"
echo " QuoteSense frontend"
echo "============================================"
echo " UI:  http://127.0.0.1:3000"
echo " API: $NEXT_PUBLIC_BACKEND_URL"
echo " node_modules → $TMP_NM"
echo " First compile can take 1–3 min. Wait for Ready / http://127.0.0.1:3000"
echo " Ctrl+C to stop."
echo "============================================"
echo ""

exec ./node_modules/.bin/next dev --hostname 127.0.0.1 --port 3000 --webpack
