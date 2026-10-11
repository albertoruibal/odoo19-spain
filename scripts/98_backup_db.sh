#!/bin/bash
# Full logical backup of the Odoo database (pg_dump custom format).
# The dump is written to the untracked backup/ folder at the project root.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; . ./.env; set +a

BACKUP_DIR="backup"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/${ODOO_DB}_${STAMP}.dump"

docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
    pg_dump -U "$POSTGRES_USER" -d "$ODOO_DB" -Fc > "$FILE"

echo "Backup written to $FILE"
