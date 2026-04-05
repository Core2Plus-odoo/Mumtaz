FROM odoo:19

USER root

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY addons /mnt/extra-addons
COPY config/odoo.conf /etc/odoo/odoo.conf.tmpl
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER odoo

CMD ["/usr/local/bin/docker-entrypoint.sh"]
