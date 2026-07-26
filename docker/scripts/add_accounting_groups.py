#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reapply all accounting fixes after a database recreation in Odoo 19 Community.

This script performs the following in one run:
  1. Grants 'Show Accounting Features - Readonly' (account.group_account_readonly)
     to the target user so the Chart of Accounts / Journals / Journal Entries
     menus and the Account column on invoice lines become visible.
  2. Grants 'Show Full Accounting Features' (account.group_account_user) so the
     Post button, Journal Items tab, reports, etc. are unlocked.

These are all needed because Odoo 19 Community Edition ships only the Invoicing
app (account module); full Accounting is Enterprise-only and many
accounting-only UI elements are gated behind groups/actions that are not
exposed by default.

Usage (run inside the odoo19 container):
    docker exec odoo19-odoo19-1 python3 /opt/scripts/add_accounting_groups.py
    docker exec odoo19-odoo19-1 python3 /opt/scripts/add_accounting_groups.py --dry-run
    docker exec odoo19-odoo19-1 python3 /opt/scripts/add_accounting_groups.py --target-login user@domain.com
"""

import sys

from _odoo_shell import base_argparser, env_scope, log


def resolve_xmlid(env, xmlid):
    """Return (model, res_id) for an xmlid like 'account.group_account_readonly'."""
    module, name = xmlid.split(".", 1)
    data = env["ir.model.data"].search(
        [("module", "=", module), ("name", "=", name)], limit=1
    )
    if not data:
        return None, None
    return data.model, data.res_id


def grant_group(env, user, group_xmlid, dry_run):
    """Grant a group to a user if not already present. Returns True if changed."""
    model, group_id = resolve_xmlid(env, group_xmlid)
    if not group_id or model != "res.groups":
        print(f"  [SKIP] cannot resolve {group_xmlid!r}")
        return False
    group = env["res.groups"].browse(group_id)
    if group in user.group_ids:
        print(f"  [OK]   {user.login} already has '{group.name}' ({group_xmlid})")
        return False
    if dry_run:
        print(f"  [DRY]  would add '{group.name}' ({group_xmlid}) to {user.login}")
        return False
    user.write({"group_ids": [(4, group.id)]})
    print(f"  [ADD]  '{group.name}' ({group_xmlid}) -> {user.login}")
    return True


def main():
    args = base_argparser(
        "Reapply all accounting fixes after a DB recreation in Odoo 19.",
        dry_run=True,
        target_login=True,
    ).parse_args()

    if not args.target_login:
        raise SystemExit("No target user: set $ODOO_USER or pass --target-login.")

    # update_module=True refreshes the module list so newly added addons are
    # discovered, then builds the registry.
    log(f"\n=== Reapplying accounting fixes on database '{args.db}' ===\n")
    with env_scope(args.db, update_module=True) as env:
        log("[1/2] Granting accounting groups to user "
            f"'{args.target_login}'...")
        user = env["res.users"].search(
            [("login", "=", args.target_login)], limit=1
        )
        if not user:
            print(f"  [ERROR] no user found with login {args.target_login!r}")
            sys.exit(1)
        log(f"  Target user: {user.name} (id={user.id})")
        grant_group(env, user, "account.group_account_readonly", args.dry_run)
        grant_group(env, user, "account.group_account_user", args.dry_run)

    log("\n=== Done ===")
    log("Next steps:")
    log("  1. Restart Odoo:  docker restart odoo19-odoo19-1")
    log("  2. Log out and back in (or hard-reload the browser).")
    log("  3. Verify:")
    log("     - Chart of Accounts / Journals menus visible under Accounting")
    log("     - Account column shown on invoice lines")


if __name__ == "__main__":
    main()