#!/usr/bin/env bash
# Smoke-test seed-match-only MA updates on QA (or local).
#
# Prerequisites:
#   1. MA table reseeded to 243 rows (seed_market_moving_averages_full_weight1.sql)
#   2. MARKET_RATE_UPDATES_ENABLED=true on the backend
#   3. Deploy includes allow_insert=False finalize path
#
# Usage:
#   ./scripts/curl_ma_seed_match_smoke.sh
#   QS_BACKEND=http://127.0.0.1:8001 ./scripts/curl_ma_seed_match_smoke.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${QS_BACKEND:-https://tatvaops-quotesense-qa.onrender.com}"
FIX="$ROOT/backend/data/fixtures"

echo "== backend: $HOST =="
curl -sS "$HOST/api/health" | head -c 400; echo

echo ""
echo "== A) MATCHED pricing method (should UPDATE existing seed row) =="
echo "   Expect: quotes_applied>=1, bundles_updated>=1, seed_match_only=true"
# Unique quote number each run so idempotency does not skip
MATCH_FILE="$(mktemp)"
python3 - <<PY
import json, time, pathlib
src = pathlib.Path("$FIX/finalize_match_pm.json")
q = json.loads(src.read_text())
q["quoteNumber"] = f"CURL-MATCH-{int(time.time())}"
pathlib.Path("$MATCH_FILE").write_text(json.dumps(q))
print(q["quoteNumber"])
PY
curl -sS -X POST "$HOST/api/market-rate/apply-finalized" \
  -H "Content-Type: application/json" \
  --data-binary @"$MATCH_FILE"
echo
rm -f "$MATCH_FILE"

echo ""
echo "== B) MISMATCHED pricing method (service+sub match, PM differs) =="
echo "   Expect: quotes_applied may be 1, but bundles_updated=0 (no INSERT)"
MISMATCH_FILE="$(mktemp)"
python3 - <<PY
import json, time, pathlib
src = pathlib.Path("$FIX/finalize_mismatch_pm.json")
q = json.loads(src.read_text())
q["quoteNumber"] = f"CURL-MISMATCH-{int(time.time())}"
pathlib.Path("$MISMATCH_FILE").write_text(json.dumps(q))
print(q["quoteNumber"])
PY
curl -sS -X POST "$HOST/api/market-rate/apply-finalized" \
  -H "Content-Type: application/json" \
  --data-binary @"$MISMATCH_FILE"
echo
rm -f "$MISMATCH_FILE"

echo ""
echo "Then in Supabase SQL:"
echo "  SELECT count(*) FROM market_moving_averages;           -- still 243"
echo "  SELECT sub_service, pricing_method, rate_moving_average, weight, last_session_id"
echo "  FROM market_moving_averages"
echo "  WHERE sub_service = '2D Floor Planning' AND service_type = 'ESSENTIAL';"
echo "  -- MATCH case: rate/weight changed, last_session_id like finalize:CURL-MATCH-*"
echo "  -- MISMATCH: no new 'Per Plate' row"
