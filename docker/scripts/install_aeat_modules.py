#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Install the AEAT modules used by the database into an Odoo 19 instance.

Modules (with dependencies resolved automatically by Odoo):
    l10n_es_aeat
    l10n_es_aeat_mod130
    l10n_es_aeat_mod303
    l10n_es_aeat_mod349
    l10n_es_aeat_mod390

Usage (run inside the odoo19 container):
    python3 install_aeat_modules.py
    python3 install_aeat_modules.py --db <ODOO_DB>
"""

import sys

from _odoo_shell import base_argparser, env_scope, log


MODULES_TO_INSTALL = [
    "l10n_es_aeat",
    "l10n_es_aeat_mod130",
    "l10n_es_aeat_mod303",
    "l10n_es_aeat_mod349",
    "l10n_es_aeat_mod390",
]


def main():
    args = base_argparser("Install AEAT modules in an Odoo 19 database.").parse_args()

    with env_scope(args.db, update_module=True) as env:
        Module = env["ir.module.module"]

        existing = Module.search_read(
            [("name", "in", MODULES_TO_INSTALL)],
            ["name", "state"],
        )
        by_name = {m["name"]: m["state"] for m in existing}
        log(f"Found {len(existing)} of {len(MODULES_TO_INSTALL)} modules in the database:")
        for name in MODULES_TO_INSTALL:
            log(f"  - {name}: {by_name.get(name, 'NOT FOUND')}")

        missing = [n for n in MODULES_TO_INSTALL if n not in by_name]
        if missing:
            raise SystemExit(f"Modules not found in addons paths: {missing}")

        already = [n for n in MODULES_TO_INSTALL if by_name.get(n) == "installed"]
        to_install = [n for n in MODULES_TO_INSTALL if by_name.get(n) != "installed"]
        if already:
            log(f"Already installed: {already}")
        if not to_install:
            log("Nothing to do - all modules already installed.")
            return

        log(f"Modules to install: {to_install}")

        # Install one at a time so dependencies resolve in order and errors
        # are attributed to a specific module.
        for name in to_install:
            mod = Module.search([("name", "=", name)], limit=1)
            if not mod:
                log(f"SKIP {name}: module record not found")
                continue
            log(f"Installing {name} (id={mod.id}) ...")
            mod.button_immediate_install()
            log(f"  -> {name} installed.")

        # Verify final state.
        final = Module.search_read(
            [("name", "in", MODULES_TO_INSTALL)],
            ["name", "state"],
        )
        log("-" * 60)
        log("Final state:")
        for m in final:
            log(f"  - {m['name']}: {m['state']}")
        not_installed = [m["name"] for m in final if m["state"] != "installed"]
        if not_installed:
            log(f"WARNING: not installed: {not_installed}")
            sys.exit(1)
        log("All AEAT modules installed successfully.")


if __name__ == "__main__":
    main()