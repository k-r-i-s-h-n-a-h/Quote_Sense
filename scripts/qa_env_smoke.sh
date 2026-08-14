#!/usr/bin/env bash
# QuoteSense QA smoke — health + market-rate by-category for an environment.
# Usage:
#   ./scripts/qa_env_smoke.sh test
#   ./scripts/qa_env_smoke.sh prod
#   ./scripts/qa_env_smoke.sh dev
#   SERVICE_ID=... CATEGORY_ID=... ./scripts/qa_env_smoke.sh test
#
# Does not test OTP UI or compare UI — see docs/QA_TESTING_KT.md

set -euo pipefail

ENV_NAME="${1:-test}"
SERVICE_ID="${SERVICE_ID:-6926b1978ba6a3cfc5a191ce}"

case "$ENV_NAME" in
  test|qa)
    RENDER="${RENDER_URL:-https://tatvaops-quotesense-qa.onrender.com}"
    UI="${UI_URL:-https://testquotesense.withtatva.ai}"
    TATVA="${TATVA_API_BASE:-https://testopsapi.withtatva.ai}"
    ADMIN="${ADMIN_URL:-https://admin.testops.withtatva.ai/otp-records}"
    ;;
  prod|production)
    RENDER="${RENDER_URL:-https://tatvaops-quotesense-prod.onrender.com}"
    UI="${UI_URL:-https://quotesense.withtatva.ai}"
    TATVA="${TATVA_API_BASE:-https://opsapi.withtatva.ai}"
    ADMIN="${ADMIN_URL:-https://admin.ops.withtatva.ai/otp-records}"
    ;;
  dev)
    RENDER="${RENDER_URL:-https://tatvaops-quotesense.onrender.com}"
    UI="${UI_URL:-https://devquotesense.withtatva.ai}"
    TATVA="${TATVA_API_BASE:-https://devopsapi.withtatva.ai}"
    ADMIN="${ADMIN_URL:-https://admin.devops.withtatva.ai/otp-records}"
    ;;
  *)
    echo "Unknown env: $ENV_NAME (use test|prod|dev)" >&2
    exit 1
    ;;
esac

CATEGORY_ID="${CATEGORY_ID:-}"

have_jq=0
command -v jq >/dev/null 2>&1 && have_jq=1

echo "=== QuoteSense QA smoke ($ENV_NAME) ==="
echo "UI:     $UI"
echo "Render: $RENDER"
echo "Tatva:  $TATVA"
echo "Admin:  $ADMIN"
echo

echo "--- GET $RENDER/api/health ---"
if ! health="$(curl -sS -m 60 "$RENDER/api/health")"; then
  echo "FAIL: health request failed (Render down/cold?)" >&2
  exit 1
fi
if [[ "$have_jq" -eq 1 ]]; then
  echo "$health" | jq .
else
  echo "$health"
fi
echo

if [[ -z "$CATEGORY_ID" ]]; then
  echo "--- by-category skipped ---"
  echo "Set CATEGORY_ID to the env's Essential/Mid/Luxury quote-type ObjectId, e.g.:"
  echo "  CATEGORY_ID=6a7b0d... ./scripts/qa_env_smoke.sh $ENV_NAME"
  echo
  echo "Manual UI checks still required (see docs/QA_TESTING_KT.md):"
  echo "  1) Login on $UI → OTP must appear on $ADMIN"
  echo "  2) Compare 2 quotes → Network GET /api/progress/... must return JSON (not HTML 404)"
  exit 0
fi

BY_URL="$RENDER/api/market-rate/by-category?service_id=${SERVICE_ID}&category_id=${CATEGORY_ID}"
echo "--- GET by-category ---"
echo "$BY_URL"
if ! body="$(curl -sS -m 90 "$BY_URL")"; then
  echo "FAIL: by-category request failed" >&2
  exit 1
fi

if [[ "$have_jq" -eq 1 ]]; then
  echo "$body" | jq '{
    service_category,
    service_type,
    count,
    service_id,
    category_id,
    first_item: .items[0],
    null_pricing_ids: ([.items[]? | select(.pricing_id == null)] | length),
    null_sub_service_ids: ([.items[]? | select(.sub_service_id == null)] | length)
  }'
  count="$(echo "$body" | jq -r '.count // 0')"
else
  echo "$body" | head -c 800
  echo
  count=0
fi

echo
if [[ "$have_jq" -eq 1 ]]; then
  if [[ "$count" == "0" || "$count" == "null" ]]; then
    echo "FAIL: count=0 — empty MA for this Supabase/Render pairing (reseed or wrong DB)." >&2
    exit 2
  fi
  echo "PASS: by-category returned count=$count"
fi

echo
echo "Next (manual):"
echo "  1) Login on $UI → confirm OTP on $ADMIN"
echo "  2) Compare → progress JSON via same-origin /api/progress/{sessionId}"
echo "Done."
