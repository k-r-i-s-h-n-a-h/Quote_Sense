#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x ./venv/bin/python ]]; then
  PY=./venv/bin/python
else
  PY=python3
fi

"$PY" -m pip install -q pytest pytest-cov httpx
"$PY" -m pytest tests/ -q --cov=services --cov=main --cov-report=term-missing --cov-report=xml
echo "Wrote coverage.xml"

# A comparison that loses a vendor's money must never reach a client.
"$PY" scripts/check_reconciliation.py
