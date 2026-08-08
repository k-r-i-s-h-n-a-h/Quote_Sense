#!/usr/bin/env bash
# Apply a finalized quote payload to QA market averages.
# Usage:
#   ./scripts/apply_finalized_qa.sh path/to/quote.json
# quote.json can be: one quote object, [quotes], or { "data": [...] } / { "quotes": [...] }

set -euo pipefail
FILE="${1:-}"
HOST="${QS_BACKEND:-https://tatvaops-quotesense-qa.onrender.com}"

if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Usage: $0 /absolute/path/to/quote.json" >&2
  echo "Create the file first (save the Tatva 'data[0]' quote including workSummary)." >&2
  exit 1
fi

# Correct URL: single https, no space, file must exist
curl -sS -X POST "${HOST}/api/market-rate/apply-finalized" \
  -H "Content-Type: application/json" \
  --data-binary @"$FILE"
echo
