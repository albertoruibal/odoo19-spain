#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared bootstrap for in-process Odoo 19 helper scripts.

These scripts run inside the odoo container (via `docker exec`) and talk to
the database directly through the Odoo registry, instead of going through
the deprecated /xmlrpc and /jsonrpc HTTP endpoints.

The container's compose entrypoint exposes the database connection as the
HOST / USER / PASSWORD / PORT environment variables (see compose.yml), which
are forwarded to the Odoo config together with the on-disk /etc/odoo/odoo.conf.
"""

import argparse
import os
import sys
from contextlib import contextmanager

import odoo
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.tools import config


ODOO_CONF = "/etc/odoo/odoo.conf"


def log(msg):
    print(msg, flush=True)


def base_argparser(description, *, dry_run=False, target_login=False):
    """Build an ArgumentParser with the common --db / --verbose flags plus
    optional script-specific flags."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--db", default=os.environ.get("ODOO_DB"),
                   help="Odoo database name (default: $ODOO_DB)")
    if dry_run:
        p.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without changing anything")
    if target_login:
        p.add_argument("--target-login",
                       default=os.environ.get("ODOO_USER"),
                       help="Login of the user to act on")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def bootstrap_config(db):
    """Parse the Odoo config from /etc/odoo/odoo.conf plus the database
    connection environment variables provided by docker compose."""
    if not db:
        raise SystemExit("No database specified: set $ODOO_DB or pass --db.")

    cli_args = ["--config", ODOO_CONF, "--database", db]
    if host := os.environ.get("HOST"):
        cli_args += ["--db_host", host]
    if user := os.environ.get("USER"):
        cli_args += ["--db_user", user]
    if password := os.environ.get("PASSWORD"):
        cli_args += ["--db_password", password]
    if port := os.environ.get("PORT", "5432"):
        cli_args += ["--db_port", port]
    config.parse_config(cli_args)


@contextmanager
def env_scope(db, update_module=False):
    """Yield an Odoo api.Environment for `db`, loading/updating the registry.

    The cursor is committed and closed on exit; on error it is rolled back.
    `update_module=True` refreshes the ir.module.module list from the addons
    paths (equivalent to the old XML-RPC `update_list` call), so newly added
    addons become discoverable.
    """
    bootstrap_config(db)
    registry = Registry.new(db, update_module=update_module)
    cr = registry.cursor()
    try:
        yield api.Environment(cr, SUPERUSER_ID, {})
        cr.commit()
    except Exception:
        cr.rollback()
        raise
    finally:
        cr.close()