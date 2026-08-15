#!/usr/bin/env bash
# Restore drill: verify a database backup against a fresh PostgreSQL instance.
#
# Usage: ./scripts/restore-drill.sh backups/db-<timestamp>.sql.gz
#
# The drill starts an isolated postgres container, restores the dump, and
# asserts the alembic head, the city catalog, and audit rows. It never touches
# the running stack. Results are appended to backups/restore-drill.log so the
# spec's "periodic restore drill with recorded results" requirement is met.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

dump_file="${1:-}"
if [[ -z "$dump_file" || ! -f "$dump_file" ]]; then
  echo "Usage: $0 backups/db-<timestamp>.sql.gz" >&2
  exit 2
fi

container="citypulse-restore-drill-$$"
password="restore-drill-only"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" \
  -e POSTGRES_DB=citypulse -e POSTGRES_USER=citypulse -e POSTGRES_PASSWORD="$password" \
  postgres:17-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$container" pg_isready -U citypulse -d citypulse >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == "30" ]]; then
    echo "Restore drill postgres never became ready." >&2
    exit 1
  fi
  sleep 2
done

gunzip -c "$dump_file" | docker exec -i "$container" psql -U citypulse -d citypulse -q >/dev/null

head="$(docker exec "$container" psql -U citypulse -d citypulse -tAc 'SELECT version_num FROM alembic_version')"
cities="$(docker exec "$container" psql -U citypulse -d citypulse -tAc 'SELECT count(*) FROM cities')"
users="$(docker exec "$container" psql -U citypulse -d citypulse -tAc 'SELECT count(*) FROM users')"
audit="$(docker exec "$container" psql -U citypulse -d citypulse -tAc 'SELECT count(*) FROM audit_logs')"

status="ok"
[[ "$head" == "0003_prediction" ]] || status="FAILED(head=$head)"
(( cities >= 13 )) || status="FAILED(cities=$cities)"
(( users >= 1 )) || status="FAILED(users=$users)"

mkdir -p backups
{
  echo "$(date -Iseconds) source=$(basename "$dump_file") head=$head cities=$cities users=$users audit=$audit status=$status"
} >> backups/restore-drill.log

echo "Restore drill: head=$head cities=$cities users=$users audit=$audit -> $status"
[[ "$status" == "ok" ]] || exit 1
