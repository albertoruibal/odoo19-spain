#!/bin/bash
# Make "Source Document" (invoice_origin) visible on the vendor-bill form.
# Odoo 19 ships it with invisible="1" on account.move.form; this adds an
# inherited view showing it for in_invoice/in_refund/in_receipt.
# Safe to re-run: removes any previous copy of the same view first.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; . ./.env; set +a

cat > /tmp/show_invoice_origin.py <<'EOF'
import os
import sys
sys.path.insert(0, '/opt/scripts')
from _odoo_shell import env_scope

XML = (
    # "Source Document" (invoice_origin, e.g. a supplier's order ref) as an
    # editable label:value row right after "Bill Reference" (ref).
    # Odoo 19 ships invoice_origin invisible in the Other Info "Invoice" group
    # (out_* only). A plain <field> in header_left_group auto-pairs its label.
    '<data>'
    '  <xpath expr="//group[@id=&quot;header_left_group&quot;]/field[@name=&quot;ref&quot;][contains(@invisible, &quot;in_receipt&quot;)]" position="after">'
    '    <field name="invoice_origin" readonly="0" force_save="1" invisible="move_type not in (&quot;in_invoice&quot;, &quot;in_receipt&quot;, &quot;in_refund&quot;)"/>'
    '  </xpath>'
    '  <xpath expr="//group[@name=&quot;sale_info_group&quot;]/field[@name=&quot;invoice_origin&quot;]" position="attributes">'
    '    <attribute name="invisible">1</attribute>'
    '  </xpath>'
    '</data>'
)
NAME = 'account.move.form.show_invoice_origin_vendor'

with env_scope(os.environ['ODOO_DB']) as env:
    V = env['ir.ui.view'].sudo()
    old = V.search([('name', '=', NAME)])
    if old:
        old.unlink()
    V.create({
        'name': NAME,
        'model': 'account.move',
        'inherit_id': env.ref('account.view_move_form').id,
        'mode': 'extension',
        'priority': 99,
        'arch_db': XML,
    })
    env.cr.commit()
    print('Source Document field is now visible on vendor bills (view: %s)' % NAME)
EOF

docker cp /tmp/show_invoice_origin.py odoo-spain-odoo19-1:/opt/scripts/show_invoice_origin.py
docker compose exec -T odoo19 python3 /opt/scripts/show_invoice_origin.py 2>&1 | grep -v "INFO\|WARN"
