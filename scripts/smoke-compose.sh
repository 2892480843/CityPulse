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

# --- End-to-end data journey: upload -> validate -> commit -> predict ->
# --- backtest -> action draft -> submit -> operator approve.
CITYPULSE_DATABASE_URL='postgresql+psycopg://citypulse:local-development-database-password@postgres:5432/citypulse' \
  "${compose[@]}" run --rm -T api \
  python -m citypulse.identity.bootstrap \
  --username smoke-analyst --password 'signal-keeper-88' --roles analyst
CITYPULSE_DATABASE_URL='postgresql+psycopg://citypulse:local-development-database-password@postgres:5432/citypulse' \
  "${compose[@]}" run --rm -T api \
  python -m citypulse.identity.bootstrap \
  --username smoke-operator --password 'market-ops-66' --roles operator

python3 - > /tmp/citypulse-smoke-panel.csv <<'PYEOF'
from datetime import date, timedelta

today = date.today()
PROFILE = {"content_growth": 100, "search_growth": 96, "event_trigger": 90,
           "accessibility": 75, "supply_capacity": 68, "weather_fit": 78,
           "novelty": 92, "cross_region_spread": 86}
START = {m: v * 0.45 for m, v in PROFILE.items()}
print("city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at")
for code, peak in (("222401", 76.7), ("370300", 40.0)):
    scale = peak / 88.08
    for offset in range(20, 0, -1):
        day = today - timedelta(days=offset)
        ramp = max(0.0, min(1.0, (20 - offset) / 18))
        available = f"{(day + timedelta(days=1)).isoformat()}T08:00:00+08:00"
        published = f"{day.isoformat()}T18:00:00+08:00"
        src = f"https://example.gov.cn/smoke/{code}"
        for metric, top in PROFILE.items():
            value = (START[metric] + (top - START[metric]) * ramp) * scale
            print(f"{code},{day.isoformat()},{metric},{round(value, 1)},{available},{src},{published},{available}")
        print(f"{code},{day.isoformat()},risk_pressure,26,{available},{src},{published},{available}")
PYEOF

panel_rows=$(wc -l < /tmp/citypulse-smoke-panel.csv)
if (( panel_rows < 40 )); then
  echo "Generated panel looks too small ($panel_rows lines)." >&2
  exit 1
fi

curl --fail --silent -c /tmp/citypulse-smoke-analyst.txt -H 'Content-Type: application/json' \
  -d '{"username":"smoke-analyst","password":"signal-keeper-88"}' \
  "http://127.0.0.1:${http_port}/api/v1/auth/login" | grep '"username":"smoke-analyst"'
analyst_csrf=$(grep citypulse_csrf /tmp/citypulse-smoke-analyst.txt | awk '{print $7}')
analyst_auth=(-b /tmp/citypulse-smoke-analyst.txt -H "X-CSRF-Token: ${analyst_csrf}")

dataset_id=$(curl --fail --silent "${analyst_auth[@]}" \
  -F "file=@/tmp/citypulse-smoke-panel.csv" \
  -F "source_name=冒烟面板" -F "legal_basis=公开统计" \
  "http://127.0.0.1:${http_port}/api/v1/datasets" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["dataset"]["id"])')

curl --fail --silent "${analyst_auth[@]}" -X POST \
  "http://127.0.0.1:${http_port}/api/v1/datasets/${dataset_id}/validate" \
  | grep '"status":"valid"'
curl --fail --silent "${analyst_auth[@]}" -X POST \
  "http://127.0.0.1:${http_port}/api/v1/datasets/${dataset_id}/commit" \
  | grep '"status":"committed"'

run_id=$(curl --fail --silent "${analyst_auth[@]}" -H 'Content-Type: application/json' \
  -d '{"window_days":14}' "http://127.0.0.1:${http_port}/api/v1/prediction-runs" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="succeeded" and d["city_count"]==2; print(d["id"])')
result_id=$(curl --fail --silent -b /tmp/citypulse-smoke-analyst.txt \
  "http://127.0.0.1:${http_port}/api/v1/prediction-runs/${run_id}/results" \
  | python3 -c 'import json,sys; items=json.load(sys.stdin)["items"]; top=items[0]; assert top["city_code"]=="222401" and top["action_priority"]=="high"; print(top["id"])')

smoke_t0=$(date +%F)
curl --fail --silent "${analyst_auth[@]}" -H 'Content-Type: application/json' \
  -d "{\"t0\":\"${smoke_t0}\",\"target_city_codes\":[\"222401\"],\"control_city_codes\":[\"370300\"],\"window_days\":14}" \
  "http://127.0.0.1:${http_port}/api/v1/backtest-runs" \
  | grep '"status":"succeeded"'

plan_id=$(curl --fail --silent "${analyst_auth[@]}" -H 'Content-Type: application/json' \
  -d "{\"prediction_result_id\":\"${result_id}\"}" \
  "http://127.0.0.1:${http_port}/api/v1/action-plans" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="draft"; print(d["id"])')
curl --fail --silent "${analyst_auth[@]}" -X POST \
  "http://127.0.0.1:${http_port}/api/v1/action-plans/${plan_id}/submit" \
  | grep '"status":"pending_review"'

curl --fail --silent -c /tmp/citypulse-smoke-operator.txt -H 'Content-Type: application/json' \
  -d '{"username":"smoke-operator","password":"market-ops-66"}' \
  "http://127.0.0.1:${http_port}/api/v1/auth/login" | grep '"username":"smoke-operator"'
operator_csrf=$(grep citypulse_csrf /tmp/citypulse-smoke-operator.txt | awk '{print $7}')
curl --fail --silent -b /tmp/citypulse-smoke-operator.txt -H "X-CSRF-Token: ${operator_csrf}" \
  -H 'Content-Type: application/json' -d '{"comment":"smoke approve"}' -X POST \
  "http://127.0.0.1:${http_port}/api/v1/action-plans/${plan_id}/approve" \
  | grep '"status":"approved"'

curl --fail --silent -b /tmp/citypulse-smoke-analyst.txt \
  "http://127.0.0.1:${http_port}/api/v1/jobs" \
  | grep '"job_type":"prediction_run"'
rm -f /tmp/citypulse-smoke-cookies.txt /tmp/citypulse-smoke-analyst.txt \
  /tmp/citypulse-smoke-operator.txt /tmp/citypulse-smoke-panel.csv

expected_head=$(ls apps/api/migrations/versions/*.py | sed -E 's|.*/([0-9a-z_]+)\.py|\1|' | sort | tail -1)
"${compose[@]}" exec -T postgres \
  psql -U citypulse -d citypulse -tAc 'SELECT version_num FROM alembic_version' \
  | grep -x "$expected_head"
"${compose[@]}" exec -T postgres \
  psql -U citypulse -d citypulse -tAc "SELECT count(*) FROM audit_logs WHERE action='login_succeeded'" \
  | grep -q '[1-9]'
"${compose[@]}" exec -T postgres \
  psql -U citypulse -d citypulse -tAc "SELECT count(*) FROM signal_observations WHERE city_code='222401'" \
  | grep -q '[1-9]'
"${compose[@]}" exec -T worker celery -A citypulse.worker:celery_app inspect ping
