#!/usr/bin/env bash
# Force-stop QuoteSense local frontend + backend (ports 3000 / 8001).
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Force-stopping QuoteSense (ports 3000, 8001)…"

for port in 3000 8001; do
  pids="$(lsof -nP -tiTCP:${port} -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "  kill -9 on port $port: $pids"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
done

for pat in \
  'uvicorn main:app' \
  'next dev --hostname 127.0.0.1 --port 3000' \
  'npm exec next dev' \
  'node .*next/dist/bin/next'
do
  if pkill -9 -f "$pat" 2>/dev/null; then
    echo "  pkill: $pat"
  fi
done

sleep 1

still3000="$(lsof -nP -tiTCP:3000 -sTCP:LISTEN 2>/dev/null || true)"
still8001="$(lsof -nP -tiTCP:8001 -sTCP:LISTEN 2>/dev/null || true)"

if [[ -n "$still3000$still8001" ]]; then
  echo "⚠️  Still bound: 3000=[$still3000] 8001=[$still8001]"
  exit 1
fi

echo "✅ Ports 3000 and 8001 are free."
echo "Start backend:  cd $ROOT/backend && ./run_dev.sh"
echo "Start frontend: cd $ROOT/frontend && ./run_dev.sh"
