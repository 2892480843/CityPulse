#!/usr/bin/env bash
# Create a timestamped backup of the PostgreSQL database and the uploads volume.
#
# Usage: ./scripts/backup.sh [output_dir]
#
# The database is dumped via pg_dump inside the running postgres container; the
# uploads volume is archived through the api container (files are owned by the
# non-root citypulse user). A manifest with SHA-256 checksums is written next
# to the archives so restores can be verified.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

output_dir="${1:-backups}"
timestamp="$(date +%Y%m%d-%H%M%S)"
env_file="${CITYPULSE_ENV_FILE:-.env}"

test -f "$env_file" || { echo "Missing $env_file (copy .env.example first)." >&2; exit 2; }
mkdir -p "$output_dir"

db_archive="$output_dir/db-$timestamp.sql.gz"
uploads_archive="$output_dir/uploads-$timestamp.tar.gz"

docker compose --env-file "$env_file" exec -T postgres \
  pg_dump -U citypulse -d citypulse --no-owner --no-privileges \
  | gzip > "$db_archive"

docker compose --env-file "$env_file" exec -T api \
  tar czf - -C /app/var/uploads . > "$uploads_archive"

manifest="$output_dir/manifest-$timestamp.txt"
{
  echo "created_at=$(date -Iseconds)"
  shasum -a 256 "$db_archive" "$uploads_archive"
  echo "db_rows="
  docker compose --env-file "$env_file" exec -T postgres \
    psql -U citypulse -d citypulse -tAc \
    "SELECT 'cities=' || count(*) FROM cities"
} > "$manifest"

echo "Backup written to $output_dir:"
ls -lh "$db_archive" "$uploads_archive" | awk '{print $9, $5}'
echo "Manifest: $manifest"
