#!/usr/bin/env bash
# End-to-end verification of the Automator↔Auditor loop.
#
# Tests: submit-merkur (dry-run) → COMPLETED + BenefitUsage written + idempotency.
# Requires: docker compose stack running with MERKUR_DRY_RUN=true.
set -euo pipefail

API="http://localhost:8000"
USER_ID="00000000-0000-0000-0000-000000000001"
USER_EMAIL="e2e@example.com"
AMOUNT="24.50"

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }
info() { echo -e "${YELLOW}→${NC} $*"; }

# ── helpers ──────────────────────────────────────────────────────────────────
psql_exec() {
  docker compose exec -T postgres psql -U kaiserclaim -t -c "$1" 2>/dev/null | grep -v '^\s*$' | head -1 | xargs
}

poll_status() {
  local id="$1" target="$2" deadline=$((SECONDS + 60)) prev=""
  while [[ $SECONDS -lt $deadline ]]; do
    local s
    s=$(curl -sf "$API/api/v1/invoices/$id?user_id=$USER_ID" | jq -r '.status' 2>/dev/null || echo "error")
    if [[ "$s" != "$prev" ]]; then info "  status: $s"; prev="$s"; fi
    if [[ "$s" == "$target" ]]; then return 0; fi
    sleep 2
  done
  fail "Timed out waiting for $target (last: $prev)"
}

# ── 1. seed user ─────────────────────────────────────────────────────────────
info "1. Seeding test user..."
psql_exec "INSERT INTO users (id, email) VALUES ('$USER_ID', '$USER_EMAIL') ON CONFLICT DO NOTHING;" >/dev/null
ok "User ready"

# ── 2. create contract ───────────────────────────────────────────────────────
info "2. Creating insurance contract..."
CONTRACT=$(curl -sf -X POST "$API/api/v1/contracts/?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"provider_name":"Merkur Test","policy_number":"TEST-001"}')
CONTRACT_ID=$(echo "$CONTRACT" | jq -r '.id')
[[ "$CONTRACT_ID" != "null" && -n "$CONTRACT_ID" ]] || fail "Contract creation failed: $CONTRACT"
ok "Contract: $CONTRACT_ID"

# ── 3. create benefit rule ───────────────────────────────────────────────────
info "3. Creating benefit rule (Medikamente, €200 YEARLY)..."
RULE=$(curl -sf -X POST "$API/api/v1/contracts/$CONTRACT_ID/benefits?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"benefit_name":"Medikamente","limit_amount":200.0,"limit_type":"YEARLY"}')
RULE_ID=$(echo "$RULE" | jq -r '.id')
[[ "$RULE_ID" != "null" && -n "$RULE_ID" ]] || fail "Benefit rule creation failed: $RULE"
ok "Benefit rule: $RULE_ID (limit €200)"

# ── 4. seed invoice directly at READY_FOR_MERKUR with known amount ───────────
info "4. Seeding invoice at READY_FOR_MERKUR with amount=$AMOUNT..."
INVOICE_ID=$(psql_exec "
  INSERT INTO invoices (id, user_id, file_path, amount, date, benefit_rule_id, status)
  VALUES (
    gen_random_uuid(),
    '$USER_ID',
    '/mnt/storage/test-receipt.jpg',
    $AMOUNT,
    NOW(),
    '$RULE_ID',
    'READY_FOR_MERKUR'
  )
  RETURNING id;
")
[[ -n "$INVOICE_ID" ]] || fail "Invoice seed failed"
ok "Invoice: $INVOICE_ID"

# ── 5. trigger submit-merkur ─────────────────────────────────────────────────
info "5. Triggering Merkur submission (dry-run)..."
TRIGGER_STATUS=$(curl -sf -X POST "$API/api/v1/invoices/$INVOICE_ID/submit-merkur?user_id=$USER_ID" | jq -r '.status')
info "  immediate status: $TRIGGER_STATUS"

# ── 6. poll until COMPLETED ───────────────────────────────────────────────────
info "6. Polling until COMPLETED..."
poll_status "$INVOICE_ID" "COMPLETED"
ok "Invoice reached COMPLETED"

# ── 7. verify BenefitUsage row exists ─────────────────────────────────────────
info "7. Verifying BenefitUsage row in DB..."
USAGE_COUNT=$(psql_exec "SELECT COUNT(*) FROM benefit_usages WHERE invoice_id='$INVOICE_ID';")
[[ "$USAGE_COUNT" == "1" ]] || fail "Expected 1 BenefitUsage row, got: $USAGE_COUNT"
USAGE_AMOUNT=$(psql_exec "SELECT amount_used FROM benefit_usages WHERE invoice_id='$INVOICE_ID';")
ok "BenefitUsage created: amount_used=$USAGE_AMOUNT"

# ── 8. verify quota via API ────────────────────────────────────────────────────
info "8. Checking benefit quota via GET /contracts/$CONTRACT_ID/benefits..."
BENEFITS=$(curl -sf "$API/api/v1/contracts/$CONTRACT_ID/benefits?user_id=$USER_ID")
AMOUNT_USED=$(echo "$BENEFITS" | jq -r '.[0].amount_used')
AMOUNT_REMAINING=$(echo "$BENEFITS" | jq -r '.[0].amount_remaining')
[[ "$AMOUNT_USED" == "24.5" || "$AMOUNT_USED" == "24.50" ]] || fail "Expected amount_used=24.5, got: $AMOUNT_USED"
ok "amount_used=$AMOUNT_USED, amount_remaining=$AMOUNT_REMAINING (was €200)"

# ── 9. idempotency: re-trigger submit-merkur, confirm no double-count ─────────
info "9. Re-triggering submit-merkur (idempotency check)..."
# Reset status to READY_FOR_MERKUR so trigger is accepted
psql_exec "UPDATE invoices SET status='READY_FOR_MERKUR' WHERE id='$INVOICE_ID';" >/dev/null
curl -sf -X POST "$API/api/v1/invoices/$INVOICE_ID/submit-merkur?user_id=$USER_ID" >/dev/null
poll_status "$INVOICE_ID" "COMPLETED"
USAGE_COUNT2=$(psql_exec "SELECT COUNT(*) FROM benefit_usages WHERE invoice_id='$INVOICE_ID';")
[[ "$USAGE_COUNT2" == "1" ]] || fail "Idempotency broken: expected 1 row, got $USAGE_COUNT2"
ok "Idempotency confirmed: still 1 BenefitUsage row after re-trigger"

# ── 10. regression: invoice without benefit_rule_id reaches COMPLETED, no usage row ──
info "10. Regression: invoice with no benefit_rule_id → COMPLETED, no BenefitUsage..."
INVOICE2_ID=$(psql_exec "
  INSERT INTO invoices (id, user_id, file_path, amount, date, status)
  VALUES (gen_random_uuid(), '$USER_ID', '/mnt/storage/no-benefit.jpg', 10.0, NOW(), 'READY_FOR_MERKUR')
  RETURNING id;
")
curl -sf -X POST "$API/api/v1/invoices/$INVOICE2_ID/submit-merkur?user_id=$USER_ID" >/dev/null
poll_status "$INVOICE2_ID" "COMPLETED"
USAGE_COUNT3=$(psql_exec "SELECT COUNT(*) FROM benefit_usages WHERE invoice_id='$INVOICE2_ID';")
[[ "$USAGE_COUNT3" == "0" ]] || fail "Expected 0 BenefitUsage rows for no-benefit invoice, got $USAGE_COUNT3"
ok "No BenefitUsage created for invoice without benefit_rule_id"

# ── done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}All checks passed.${NC} The Automator↔Auditor loop is working end-to-end."
echo ""
echo "Summary:"
echo "  • Invoice with benefit_rule_id → COMPLETED + BenefitUsage(amount_used=$AMOUNT_USED)"
echo "  • Quota reflected in GET /contracts/{id}/benefits (used=$AMOUNT_USED, remaining=$AMOUNT_REMAINING)"
echo "  • Re-trigger is idempotent (no double-counting)"
echo "  • Invoice without benefit_rule_id → COMPLETED, no BenefitUsage"
