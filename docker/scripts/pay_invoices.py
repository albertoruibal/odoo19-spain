#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Register a bank payment for every unpaid customer (out_invoice) and
vendor (in_invoice) invoice in an Odoo 19 database.

- Payments are made through the company's bank journal (Manual method).
- Each payment is dated the same as the invoice (am.invoice_date).
- Invoices are processed oldest first (ordered by invoice_date, then id).
- One payment per invoice (group_payment disabled) so reconciliation is 1:1.

Usage (run inside the odoo19 container):
    python3 pay_invoices.py
    python3 pay_invoices.py --db <ODOO_DB> --journal-code BNK1
    python3 pay_invoices.py --dry-run --limit 10
"""

import argparse
import os
import sys

from _odoo_shell import env_scope, log


def parse_args():
    p = argparse.ArgumentParser(description="Pay all unpaid Odoo 19 invoices via bank.")
    p.add_argument("--db", default=os.environ.get("ODOO_DB"),
                   help="Odoo database name (default: $ODOO_DB)")
    p.add_argument("--journal-code", default=os.environ.get("ODOO_JOURNAL_CODE", "BNK1"),
                   help="Code of the bank journal to use (default: BNK1)")
    p.add_argument("--move-types", default="out_invoice,in_invoice",
                   help="Comma-separated list of move types to pay")
    p.add_argument("--limit", type=int, default=0,
                   help="Max invoices to process (0 = all)")
    p.add_argument("--dry-run", action="store_true",
                   help="List what would be paid without creating payments")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    with env_scope(args.db) as env:
        Move = env["account.move"]
        Journal = env["account.journal"]
        Register = env["account.payment.register"]

        journal = Journal.search(
            [("code", "=", args.journal_code), ("type", "=", "bank")],
            limit=1,
        )
        if not journal:
            raise SystemExit(f"No bank journal with code {args.journal_code!r} found.")
        log(f"Using bank journal: {journal.code} - {journal.name} (id={journal.id})")

        move_types = [t.strip() for t in args.move_types.split(",") if t.strip()]
        domain = [
            ("move_type", "in", move_types),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
        ]
        invoice_ids = Move.search(
            domain,
            order="invoice_date asc, id asc",
            limit=args.limit or None,
        )
        log(f"Found {len(invoice_ids)} unpaid invoice(s) to process "
            f"(types={move_types}, limit={args.limit or 'all'}).")
        if not invoice_ids:
            return

        invoices = Move.read(
            invoice_ids.ids,
            ["name", "move_type", "invoice_date", "partner_id",
             "amount_total", "amount_residual", "payment_state"],
        )

        ok = 0
        failed = []
        for inv in invoices:
            partner = inv.get("partner_id") or (None, None)
            line = (f"{inv['name']:>12} | {inv['move_type']:<11} | "
                    f"{inv['invoice_date']} | {partner[1] if partner else '-':<30} | "
                    f"residual={inv['amount_residual']:.2f} ({inv['payment_state']})")
            if args.dry_run:
                log(f"DRY-RUN would pay: {line}")
                continue
            try:
                # One payment per invoice (group_payment disabled) -> 1:1 reconcile.
                wizard = Register.with_context(
                    active_model="account.move",
                    active_ids=[inv["id"]],
                    active_id=inv["id"],
                ).create({
                    "journal_id": journal.id,
                    "payment_date": inv["invoice_date"],
                })
                wizard.action_create_payments()
                log(f"PAID: {line}")
                ok += 1
            except Exception as e:
                print(f"FAILED: {line}\n      -> {e}", file=sys.stderr)
                failed.append((inv["name"], str(e)))

        log("-" * 78)
        log(f"Done. Paid: {ok}, Failed: {len(failed)}, "
            f"Total processed: {len(invoices)}.")
        if failed:
            log("Failures:")
            for name, err in failed:
                log(f"  - {name}: {err}")
            sys.exit(1)


if __name__ == "__main__":
    main()