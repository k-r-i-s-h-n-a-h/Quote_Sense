#!/usr/bin/env bash
# Free port 3000 then start Next.js (safe to run even if nothing is listening)
set -e
cd "$(dirname "$0")/.."

if lsof -ti :3000 >/dev/null 2>&1; then
  echo "Stopping process on port 3000…"
  lsof -ti :3000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

rm -f .next/dev/lock

exec next dev --hostname 127.0.0.1 --port 3000
