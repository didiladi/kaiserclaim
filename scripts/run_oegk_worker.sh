#!/usr/bin/env bash
# Desktop worker for the ÖGK queue (headed browser, ID-Austria 2FA).
#
# The cluster worker never consumes the `oegk` queue, so READY_FOR_OEGK invoices
# wait until this runs. It talks to the cluster's Redis and Postgres through
# kubectl port-forward, and fetches invoice files over the API.
#
# Usage:
#   export DATABASE_URL='postgresql+asyncpg://kaiserclaim:<password>@localhost:15432/kaiserclaim'
#   export API_TOKEN='<same token as the cluster secret>'
#   scripts/run_oegk_worker.sh
#
# DATABASE_URL must be set by you (the password is in the cluster secret; this
# script never reads it). Stop with Ctrl-C.
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL to the port-forwarded Postgres URL (localhost:15432)}"

cd "$(dirname "$0")/.."
NS=kaiserclaim
PY="${PYTHON:-.venv/bin/python}"

# The database is the shared Postgres in namespace `family`, not in kaiserclaim.
kubectl -n family port-forward svc/postgres-postgresql 15432:5432 >/dev/null &
PF_DB=$!
kubectl -n "$NS" port-forward svc/redis-svc 16379:6379 >/dev/null &
PF_REDIS=$!
trap 'kill $PF_DB $PF_REDIS 2>/dev/null || true' EXIT
sleep 3

export CELERY_BROKER_URL="redis://localhost:16379/0"
export CELERY_RESULT_BACKEND="redis://localhost:16379/1"
export REDIS_URL="$CELERY_BROKER_URL"
export API_BASE_URL="${API_BASE_URL:-https://kaiserclaim.home}"
: "${API_TOKEN:?set API_TOKEN (same value as the cluster secret) so invoice files can be fetched}"
export OEGK_HEADLESS=false
export STORAGE_ROOT="${STORAGE_ROOT:-$HOME/.kaiserclaim-oegk}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-unused-on-this-worker}"
export SECRET_KEY="${SECRET_KEY:-unused-on-this-worker}"
mkdir -p "$STORAGE_ROOT"

exec "$PY" -m celery -A workers.tasks.celery_app worker \
  -Q oegk --concurrency=1 --hostname="oegk@%h" --loglevel=info
