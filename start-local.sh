#!/usr/bin/env bash
# QuoteSense local dev — run backend + frontend in two terminals, or use this helper.
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo " QuoteSense — local dev"
echo "============================================"
echo ""
echo "Run these in TWO separate terminals:"
echo ""
echo "  Terminal 1 (backend):"
echo "    cd $ROOT/backend && ./run_dev.sh"
echo ""
echo "  Terminal 2 (frontend):"
echo "    cd $ROOT/frontend && ./run_dev.sh"
echo ""
echo "Before first run, edit backend/.env with your real API keys."
echo "Then open: http://localhost:3000"
echo ""
