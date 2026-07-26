#!/bin/bash
# Set "Product Unit" decimal precision to 3 so re-imported invoice quantities
# (e.g. QUOBIS 0.666, 0.904, 0.952) keep full precision instead of rounding to 2 dp.
# Mirrors the UI change: Settings > Technical > Decimal Accuracy > "Product Unit" > Digits=3.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
set -a; . ./.env; set +a

docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$ODOO_DB" -c \
  "UPDATE decimal_precision SET digits=3 WHERE name='Product Unit';"

docker compose restart odoo19