# AGENTS.md — working with the Odoo 19 stack in this repo

Guidance for coding agents (and humans driving them) interacting with the
dockerized Odoo 19 instance. Everything here is generic infrastructure
knowledge — quarter-specific accounting procedures live in the
`quarterly-accounting` skill, not here.

## Stack

- Odoo 19 Community + OCA l10n-spain (AEAT modules), custom image
  `odoo19/` (Dockerfile clones OCA addons at build, branch `19.0`),
  `postgres:18.6`.
- `docker compose up -d`; containers `odoo-spain-odoo19-1` (web :10019,
  longpolling :20019) and `odoo-spain-db-1` (postgres, internal 5432).
- Database name, creds and users come from `.env` (gitignored):
  `POSTGRES_USER`, `POSTGRES_PASSWORD`, `ODOO_DB`, `ADMIN_PASSWORD`,
  `ODOO_USER`, `ODOO_PASSWORD`. Never print secret values; source the file
  and reference the vars.
- `filestore/` and `postgresql/` are bind mounts (persist across down/up).
- Web UI: `http://localhost:10019/odoo`, login `ODOO_USER`/`ODOO_PASSWORD`
  (application user; accounting UI visible after running 03).

## Read-only DB access (psql)

```bash
cd ~/workspace/odoo-spain && source .env && docker compose exec -T \
  -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$ODOO_DB" \
  -c "select ..."
```

Odoo 19 schema notes that bite:

- `account.account.code_store` is the account code (jsonb/`{"1":"62900002"}`
  style); there is no plain `code` column. Filter with
  `('code_store', '=', '62900003')`.
- `ir_ui_view.arch_db` is jsonb (per-lang keys); text-search via
  `arch_db::text`.
- Useful tables: `account_move` (header: `ref` = supplier's invoice number,
  `invoice_origin` = source document (e.g. an order ref), `invoice_date`,
  `date`, `invoice_date_due`, `state`, `name` = numbering V/C/... assigned on
  posting), `account_move_line` (join `account_account` by `account_id`),
  `account_move_line_account_tax_rel` for line↔tax.

## In-container Python (the way to write data)

No XML-RPC/JSON-RPC (deprecated in Odoo 19). Use in-process Python with the
registry bootstrapped from `/etc/odoo/odoo.conf` + compose env:

- Bootstrap module: `docker/scripts/_odoo_shell.py` — provides
  `env_scope(db, update_module=False)` yielding a SUPERUSER env, committing
  on clean exit / rolling back on exception.
- Run pattern:
  ```bash
  cd ~/workspace/odoo-spain && source .env
  docker compose exec -T -w /opt/scripts odoo19 python3 - <<'PY'
  import os
  from _odoo_shell import env_scope
  with env_scope(os.environ['ODOO_DB']) as env:
      ...
  PY
  ```
  Or put the script on disk and `docker cp` it into the container's
  `/opt/scripts/` first, then exec it. Ad-hoc per-run scripts live in
  `mobialia/` (gitignored) on the host; `docker/scripts/` keeps only the
  committed repo helpers.
- `env['account.move'].get_view()["arch"]` / `get_views([[view_id, 'form']])`
  read the MERGED view arch (verify inheritance effects server-side).

## Views / customizations

- Inherit views are rows in `ir_ui_view` (mode `extension`,
  `inherit_id` = base view id). There is a custom inherit
  `account.move.form.show_invoice_origin_vendor` (see
  `scripts/05_show_invoice_origin.sh`) that shows `invoice_origin`
  ("Source Document") editable next to "Bill Reference" on vendor bills;
  the base form ships it invisible and the field itself is
  model-`readonly=True`.
- View edits done from a separate process are not seen by running workers
  until the registry reloads: clear caches
  (`env.registry.clear_cache()` / `clear_all_caches()`), or just
  `docker compose restart odoo19` when archs don't land.
- Odoo 19 form quirks: `xpath ... @string` selectors are rejected
  ("may not use attribute 'string' as a selector"); a bare `<field>` inside
  a `group` auto-renders its own label:value cell; two copies of the same
  field name on one form conflict — hide one copy when adding another.

## Backups / safety

- `backup/` (gitignored) holds `pg_dump` custom dumps:
  `scripts/98_backup_db.sh` → `backup/<db>_<timestamp>.dump`.
- Take a backup before bulk data changes (booking scripts, imports).
- Restore path: `web/database/manager` + `ADMIN_PASSWORD`, or
  `pg_restore` for the dumps above (same Postgres version, 18).

## Maintenance scripts (host-side, numbered; run in order)

| script | does |
|---|---|
| `scripts/01_install_aeat_modules.sh` | AEAT mods (303/349/130/390...) |
| `scripts/02_install_accounting.sh` | `report_xlsx`, `account_financial_report` |
| `scripts/03_add_accounting_groups.sh` | grants `ODOO_USER` the accounting groups (needs restart; script does it) |
| `scripts/04_fix_product_unit_precision.sh` | decimal precision Product Unit = 3 |
| `scripts/05_show_invoice_origin.sh` | vendor-bill "Source Document" visibility fix (idempotent) |
| `scripts/98_backup_db.sh` | pg_dump to `backup/` |
| `scripts/99_pay_invoices.sh` | register BNK1 payments for posted unpaid invoices (1:1, same date) |

All helper flags: `--db`, `--verbose`, `--dry-run`; payment script adds
`--limit`, `--journal-code`, `--move-types`.
