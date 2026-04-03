FROM odoo:19
USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt
COPY addons /mnt/extra-addons
COPY config/odoo.conf /etc/odoo/odoo.conf
USER odoo
CMD ["odoo", "-c", "/etc/odoo/odoo.conf"]
