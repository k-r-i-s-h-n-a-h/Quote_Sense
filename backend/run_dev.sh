#!/usr/bin/env bash
# Start QuoteSense backend with live logs.
#
# Why Desktop ./venv often "sticks" on first line of uvicorn:
#   loading fastapi/main can take minutes (or thrash) when RAM is tight
#   and the project sits on Desktop/iCloud File Provider.
#
# By default we use a working cache venv at /tmp/quotesense-backend-venv
# (same packages, much faster cold start). Override with USE_PROJECT_VENV=1.
#
# Usage:
#   ./run_dev.sh
#   PORT=8002 ./run_dev.sh
#   USE_PROJECT_VENV=1 ./run_dev.sh
#   QS_RELOAD=1 ./run_dev.sh
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8001}"

if [[ ! -f .env ]]; then
  echo "❌ backend/.env missing — copy .env.example to .env and add your keys."
  exit 1
fi

# Free target port
if lsof -nP -iTCP:"$PORT" >/dev/null 2>&1; then
  echo "Stopping process on :$PORT…"
  lsof -nP -tiTCP:"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
  sleep 1
fi

CACHE_VENV="/tmp/quotesense-backend-venv"
PROJECT_VENV="$(pwd)/venv"

if [[ "${USE_PROJECT_VENV:-0}" == "1" ]]; then
  if [[ ! -x "$PROJECT_VENV/bin/python" ]]; then
    echo "❌ Project venv missing at $PROJECT_VENV"
    exit 1
  fi
  PY="$PROJECT_VENV/bin/python"
  VENV_LABEL="project ./venv (can be slow to first log)"
elif [[ -x "$CACHE_VENV/bin/python" ]]; then
  PY="$CACHE_VENV/bin/python"
  VENV_LABEL="cache $CACHE_VENV (fast cold start)"
elif [[ -x "$PROJECT_VENV/bin/python" ]]; then
  PY="$PROJECT_VENV/bin/python"
  VENV_LABEL="project ./venv"
else
  echo "Creating project venv…"
  python3 -m venv venv
  ./venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
  PY="./venv/bin/python"
  VENV_LABEL="new project ./venv"
fi

# region agent log
{
  mkdir -p ../.cursor 2>/dev/null || true
  printf '{"sessionId":"1a6040","timestamp":%s,"location":"backend/run_dev.sh","message":"starting uvicorn","data":{"port":%s,"py":"%s"},"hypothesisId":"C","runId":"dev"}\n' \
    "$(($(date +%s)*1000))" "$PORT" "$PY" >> ../.cursor/debug-1a6040.log 2>/dev/null || true
}
# endregion

echo "============================================"
echo " QuoteSense backend"
echo "============================================"
echo " Python: $PY"
echo " Venv:   $VENV_LABEL"
echo " Port:   $PORT"
echo " Health: http://127.0.0.1:${PORT}/api/health"
echo " Docs:   http://127.0.0.1:${PORT}/docs"
echo ""
echo " Wait for: Application startup complete"
echo " After that, idle (no new lines) is NORMAL."
echo " Ctrl+C to stop."
echo "============================================"
echo ""

export PYTHONUNBUFFERED=1
if [[ "${QS_RELOAD:-0}" == "1" ]]; then
  echo "⚠️  --reload: first logs may take 30–90s."
  exec env -u PYTHONPATH -u PYTHONHOME "$PY" -u -m uvicorn main:app \
    --host 127.0.0.1 --port "$PORT" --reload --log-level info
else
  exec env -u PYTHONPATH -u PYTHONHOME "$PY" -u -m uvicorn main:app \
    --host 127.0.0.1 --port "$PORT" --log-level info
fi
