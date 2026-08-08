#!/usr/bin/env bash
set -e
cd /Users/krishnahonnikhere/Desktop/tatvaops-quotesense/frontend
if lsof -nP -tiTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -nP -tiTCP:3000 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
  sleep 1
fi
echo "Starting frontend at http://127.0.0.1:3000"
exec npx next dev --hostname 127.0.0.1 --port 3000
