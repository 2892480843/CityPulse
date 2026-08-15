#!/usr/bin/env bash
set -euo pipefail

project_name="${CITYPULSE_SMOKE_PROJECT:-citypulse-smoke-$$}"
http_port="${CITYPULSE_HTTP_PORT:-18080}"
smoke_admin_password="guard-tower-2026-smoke"

if [[ ! "$project_name" =~ ^citypulse-smoke-[a-z0-9-]+$ ]]; then
  echo "CITYPULSE_SMOKE_PROJECT must start with citypulse-smoke- and contain lowercase letters, digits, or hyphens." >&2
  exit 2
fi
if [[ ! "$http_port" =~ ^[0-9]{4,5}$ ]] || (( http_port < 1024 || http_port > 65535 )); then
  echo "CITYPULSE_HTTP_PORT must be an available port from 1024 through 65535." >&2
  exit 2
fi

export CITYPULSE_ENV_FILE=.env.example
export CITYPULSE_HTTP_PORT="$http_port"
compose=(docker compose --parallel 1 --env-file .env.example -p "$project_name")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

"${compose[@]}" config --quiet
for service in api worker scheduler migrate web; do
  "${compose[@]}" build "$service"
done
"${compose[@]}" up -d postgres redis
"${compose[@]}" run --rm migrate
CITYPULSE_DATABASE_URL='postgresql+psycopg://citypulse:local-development-database-password@postgres:5432/citypulse' \
  "${compose[@]}" run --rm -T api \
  python -m citypulse.identity.bootstrap \
  --username smoke-admin --password "$smoke_admin_password" --roles admin
"${compose[@]}" up -d api worker scheduler web proxy

for attempt in $(seq 1 60); do
  if curl --fail --silent "http://127.0.0.1:${http_port}/health/ready" >/dev/null; then
    break
  fi
  if [[ "$attempt" == "60" ]]; then
    "${compose[@]}" ps
    "${compose[@]}" logs --no-color api worker postgres redis
    exit 1
  fi
  sleep 2
done

curl --fail --silent "http://127.0.0.1:${http_port}/health/live" | grep '"status":"ok"'
curl --fail --silent "http://127.0.0.1:${http_port}/health/ready" | grep '"status":"ok"'
curl --fail --silent "http://127.0.0.1:${http_port}/api/v1/system/version" | grep '"version":"0.1.0"'
curl --fail --silent "http://127.0.0.1:${http_port}/" | grep 'CityPulse'

curl --silent "http://127.0.0.1:${http_port}/api/v1/auth/me" | grep '"code":"UNAUTHENTICATED"'
curl --fail --silent -c /tmp/citypulse-smoke-cookies.txt -H 'Content-Type: application/json' \
  -d "{\"username\":\"smoke-admin\",\"password\":\"${smoke_admin_password}\"}" \
  "http://127.0.0.1:${http_port}/api/v1/auth/login" | grep '"username":"smoke-admin"'
curl --fail --silent -b /tmp/citypulse-smoke-cookies.txt \
  "http://127.0.0.1:${http_port}/api/v1/auth/me" | grep '"roles":\["admin"\]'
rm -f /tmp/citypulse-smoke-cookies.txt

"${compose[@]}" exec -T postgres \
  psql -U citypulse -d citypulse -tAc 'SELECT version_num FROM alembic_version' \
  | grep '0002_identity_data'
"${compose[@]}" exec -T postgres \
  psql -U citypulse -d citypulse -tAc "SELECT count(*) FROM audit_logs WHERE action='login_succeeded'" \
  | grep -q '[1-9]'
"${compose[@]}" exec -T worker celery -A citypulse.worker:celery_app inspect ping
