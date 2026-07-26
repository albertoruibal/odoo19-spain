FROM odoo:19

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 -b 19.0 https://github.com/OCA/l10n-spain.git                   /opt/oca-addons/l10n-spain \
 && git clone --depth 1 -b 19.0 https://github.com/OCA/account-financial-reporting.git  /opt/oca-addons/account-financial-reporting \
 && git clone --depth 1 -b 19.0 https://github.com/OCA/server-ux.git                    /opt/oca-addons/server-ux \
 && git clone --depth 1 -b 19.0 https://github.com/OCA/reporting-engine.git             /opt/oca-addons/reporting-engine

COPY scripts/ /opt/scripts/
RUN chmod +x /opt/scripts/*.py

COPY odoo.conf /etc/odoo/odoo.conf

USER odoo