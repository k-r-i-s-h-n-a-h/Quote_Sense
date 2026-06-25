#!/usr/bin/env bash
# Start QuoteSense frontend (Next.js on port 3000)
set -e
cd "$(dirname "$0")"

if [[ ! -d node_modules/next ]]; then
  echo "Installing frontend dependencies…"
  npm install
fi

# Free port 3000 if a stale Next.js process is holding it
if lsof -ti :3000 >/dev/null 2>&1; then
  echo "Stopping stale process on port 3000…"
  lsof -ti :3000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# Clear stale dev cache (fixes hung "Starting..." / ETIMEDOUT from prior runs)
rm -rf .next/dev/lock .next/cache

echo "Starting frontend at http://127.0.0.1:3000"
exec npx next dev --hostname 127.0.0.1 --port 3000
