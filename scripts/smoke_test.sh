#!/usr/bin/env bash
# Smoke test for the pharmacy short-track pipeline.
# Usage: ./scripts/smoke_test.sh /path/to/receipt.(pdf|jpg|png)
set -euo pipefail

FILE="${1:-}"
if [[ -z "$FILE" ]]; then
  echo "Usage: $0 /path/to/receipt.(pdf|jpg|png)"
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "Error: file not found: $FILE"
  exit 1
fi

API="http://localhost:8000"
USER_ID="00000000-0000-0000-0000-000000000001"
USER_EMAIL="test@example.com"

echo "==> Ensuring test user exists..."
docker compose exec postgres psql -U kaiserclaim -c \
  "INSERT INTO users (id, email) VALUES ('$USER_ID', '$USER_EMAIL') ON CONFLICT DO NOTHING;" \
  2>&1 | grep -v "^WARN"

echo "==> Uploading file via HTTP..."
RESPONSE=$(curl -sf -X POST "$API/api/v1/invoices/upload?user_id=$USER_ID" \
  -F "file=@$FILE")
echo "$RESPONSE" | jq .

INVOICE_ID=$(echo "$RESPONSE" | jq -r '.id')
if [[ -z "$INVOICE_ID" || "$INVOICE_ID" == "null" ]]; then
  echo "Error: failed to create invoice"
  exit 1
fi

echo ""
echo "==> Invoice ID: $INVOICE_ID"
echo "==> Polling status (max 3 min)..."
echo ""

DEADLINE=$((SECONDS + 180))
PREV_STATUS=""

while [[ $SECONDS -lt $DEADLINE ]]; do
  STATUS=$(curl -sf "$API/api/v1/invoices/$INVOICE_ID?user_id=$USER_ID" | jq -r '.status')

  if [[ "$STATUS" != "$PREV_STATUS" ]]; then
    echo "    $(date +%H:%M:%S)  $STATUS"
    PREV_STATUS="$STATUS"
  fi

  if [[ "$STATUS" == "READY_FOR_MERKUR" ]]; then
    echo ""
    echo "==> OCR pipeline complete. Invoice is READY_FOR_MERKUR."
    echo ""
    echo "==> Extracted metadata:"
    curl -sf "$API/api/v1/invoices/$INVOICE_ID?user_id=$USER_ID" | jq '{amount, date, provider_name}'
    exit 0
  fi

  if [[ "$STATUS" == "null" || -z "$STATUS" ]]; then
    echo "Error: could not fetch invoice status"
    exit 1
  fi

  sleep 5
done

echo ""
echo "Error: timed out after 3 minutes. Last status: $PREV_STATUS"
echo "Check worker logs: docker compose logs worker"
exit 1
