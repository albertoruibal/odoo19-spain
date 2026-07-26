#!/bin/bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
set -a; . ./.env; set +a

docker compose exec -e ODOO_DB -e ODOO_USER odoo19 \
    python3 /opt/scripts/add_accounting_groups.py

docker compose down
docker compose up -d