# Odoo 19 — Spanish accounting

This directory contains a Docker Compose setup for an **Odoo 19 Community**
instance tailored to **Spanish accounting** (`l10n_es_aeat` and related OCA
modules from [OCA/l10n-spain](https://github.com/OCA/l10n-spain)).

It is a self-contained deployment: a `postgres:18` database service and a
custom `odoo:19` image that bakes in the OCA addons, the Odoo config file and
a set of in-container helper scripts for installing modules and performing
post-install maintenance.

## Layout

```
odoo19/
├── .env                  # secrets + DB name (NOT committed, see below)
├── compose.yml           # docker compose services (db + odoo19)
├── docker/
│   ├── Dockerfile        # builds the odoo image with OCA addons + scripts
│   ├── odoo.conf         # baked-in /etc/odoo/odoo.conf
│   └── scripts/          # in-process helper scripts (copied to /opt/scripts)
│       ├── _odoo_shell.py
│       ├── install_aeat_modules.py
│       ├── install_accounting.py
│       ├── add_accounting_groups.py
│       └── pay_invoices.py
├── filestore/            # Odoo data dir (bind mount, persisted)
├── postgresql/           # PostgreSQL data dir (bind mount, persisted)
└── scripts/              # host-side setup scripts
    ├── 01_install_aeat_modules.sh
    ├── 02_install_accounting.sh
    ├── 03_add_accounting_groups.sh
    ├── 04_fix_product_unit_precision.sh
    ├── 05_backup_db.sh
    └── 99_pay_invoices.sh
```

## Quick start

1. **Create the `.env` file** (see below) — it is gitignored and required.
2. Build and start the stack:

   ```bash
   docker compose up -d --build
   ```

3. Wait for Odoo to come up, then create a company via the web UI and then run the setup scripts in order:

   ```bash
   ./scripts/01_install_aeat_modules.sh
   ./scripts/02_install_accounting.sh
   ./scripts/03_add_accounting_groups.sh
   ./scripts/04_fix_product_unit_precision.sh
   ```

4. Odoo is reachable on http://localhost:10019 (longpolling on :20019).
   Log in with the application user declared in `.env`
   (`ODOO_USER` / `ODOO_PASSWORD`).

## The `.env` file

Docker Compose loads `odoo19/.env` automatically. The file is **gitignored**
because it contains passwords. Create it with the following variables:

```dotenv
# PostgreSQL (db service)
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<choose a strong password>
POSTGRES_DB=postgres

# Odoo database name
ODOO_DB=<your-db-name>

# Odoo master/admin password.
# Sourced via the ODOO_ADMIN_PASSWD env var and used by Odoo as admin_passwd
# (database manager / create DB / restore). Do NOT put it in odoo.conf.
ADMIN_PASSWORD=<choose a strong password>

# Odoo application user (used by the helper scripts and for daily use).
# This user must already exist in the Odoo database (created from the UI on
# first run, or imported from a backup).
ODOO_USER=info@example.com
ODOO_PASSWORD=<application user password>
```

> The `compose.yml` forwards these to the container:
> `HOST=db`, `USER`/`PASSWORD` (PostgreSQL credentials, also used by the
> in-process scripts to connect to the DB), `ODOO_ADMIN_PASSWD`,
> `ODOO_DB`, `ODOO_USER` and `ODOO_PASSWORD`.

## Helper scripts

The numbered shell scripts in this directory wrap `docker exec` calls into the
running `odoo19-odoo19-1` container. They source `.env` and run the matching
Python helper from `/opt/scripts/` inside the container.

### How the Python helpers work

The helpers run **in-process** inside the Odoo container: they bootstrap the
Odoo config from `/etc/odoo/odoo.conf` plus the `HOST`/`USER`/`PASSWORD`/`PORT`
environment variables forwarded by compose, build the Odoo registry with
`Registry.new(db)`, and act through an `api.Environment` as `SUPERUSER_ID`.

This means they talk to the database directly — **no HTTP, no XML-RPC, no
JSON-RPC, no API keys**. They are not affected by the Odoo 19 deprecation of
the `/xmlrpc` and `/jsonrpc` endpoints (scheduled for removal in Odoo 22).

The shared bootstrap lives in `docker/scripts/_odoo_shell.py` and provides:
- `base_argparser(...)` — common `--db` / `--verbose` / `--dry-run` /
  `--target-login` flags.
- `bootstrap_config(db)` — assembles the Odoo config from the config file and
  the compose-provided env vars.
- `env_scope(db, update_module=False)` — context manager that loads the
  registry (optionally refreshing the module list), yields an
  `api.Environment`, and commits/rolls back on exit.

### Scripts

| # | Shell script | Python helper | What it does |
|---|---|---|---|
| 01 | `scripts/01_install_aeat_modules.sh` | `install_aeat_modules.py` | Installs the AEAT modules: `l10n_es_aeat`, `l10n_es_aeat_mod130`, `l10n_es_aeat_mod303`, `l10n_es_aeat_mod349`, `l10n_es_aeat_mod390`. Idempotent — skips modules already installed. |
| 02 | `scripts/02_install_accounting.sh` | `install_accounting.py` | Installs the OCA reporting modules: `report_xlsx`, `account_financial_report`. Idempotent. |
| 03 | `scripts/03_add_accounting_groups.sh` | `add_accounting_groups.py` | Grants `account.group_account_readonly` and `account.group_account_user` to the `ODOO_USER` so the full accounting UI (Chart of Accounts, Journals, Journal Items, Post button, reports) is visible in Odoo 19 Community, where it is gated behind groups not exposed by default. Then restarts the stack. Supports `--dry-run` and `--target-login`. |
| 04 | `scripts/04_fix_product_unit_precision.sh` | *(inline `psql`)* | Sets the `Product Unit` decimal precision to 3 digits via `psql` so re-imported invoice quantities (e.g. `0.666`, `0.904`) keep full precision instead of rounding to 2 dp. Mirrors Settings ▸ Technical ▸ Decimal Accuracy ▸ Product Unit ▸ Digits = 3. |
| 05 | `scripts/05_backup_db.sh` | *(inline `pg_dump`)* | Writes a full logical backup of `ODOO_DB` to `backup/<db>_<timestamp>.dump` (pg_dump custom format). The `backup/` folder is gitignored. |
| 99 | `scripts/99_pay_invoices.sh` | `pay_invoices.py` | Registers a bank payment (journal `BNK1` by default) for every posted, unpaid `out_invoice`/`in_invoice`, dated the same as the invoice and processed oldest first. One payment per invoice for 1:1 reconciliation. Supports `--dry-run`, `--limit N`, `--journal-code`, `--move-types`. |

### Running a helper directly

You can invoke any helper inside the container without the shell wrapper, e.g.
for a dry run of the payment script:

```bash
docker exec -e ODOO_DB=<your-db-name> odoo19-odoo19-1 \
    python3 /opt/scripts/pay_invoices.py --db <your-db-name> --dry-run --limit 10
```

Common flags accepted by the Python helpers:
- `--db` (default: `$ODOO_DB`)
- `--verbose` / `-v`
- `--dry-run` (`pay_invoices.py`, `add_accounting_groups.py`)
- `--target-login` (`add_accounting_groups.py`, default: `$ODOO_USER`)
- `--journal-code`, `--move-types`, `--limit` (`pay_invoices.py`)

## Configuration notes

- `docker/odoo.conf` is baked into the image at `/etc/odoo/odoo.conf`. It sets
  the OCA `addons_path`, `data_dir`, `proxy_mode`, `workers` and logging.
- The **`admin_passwd` is not in `odoo.conf`**; it is supplied at runtime via
  the `ODOO_ADMIN_PASSWD` environment variable (`ADMIN_PASSWORD` in `.env`),
  which Odoo 19 reads natively and which takes precedence over the config file.
- `filestore/` and `postgresql/` are bind-mounted from this directory so the
  database and Odoo filestore persist across `docker compose down` / `up`.
- The OCA addons are cloned at build time (branch `19.0`) into `/opt/oca-addons`
  inside the image and registered in `addons_path`. To pick up upstream changes,
  rebuild the image with `docker compose build odoo19`.

## Backing up

Run `./scripts/05_backup_db.sh` to write a full logical dump of `ODOO_DB` to
`backup/<db>_<timestamp>.dump` (pg_dump custom format). The `backup/` folder is
gitignored. Note this dumps the database only; the Odoo filestore lives in the
bind-mounted `filestore/` directory.

## Restoring a backup

To restore an existing Odoo database dump (e.g. a `.zip` from the database
manager):

1. Start the stack: `docker compose up -d --build`.
2. Open http://localhost:10019/web/database/manager and use **Restore Database**
   with the `ADMIN_PASSWORD` from `.env`.
3. Run the helper scripts `01`–`04` to ensure all modules and accounting groups
   are in place for the restored database.
