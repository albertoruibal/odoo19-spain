#!/bin/bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; . ./.env; set +a

docker compose exec -e ODOO_DB odoo19 \
    python3 /opt/scripts/install_aeat_modules.py --db "$ODOO_DB"