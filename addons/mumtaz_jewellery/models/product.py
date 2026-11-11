from odoo import fields, models

KARATS = [
    ('24', '24K'), ('22', '22K'), ('21', '21K'),
    ('18', '18K'), ('14', '14K'), ('9', '9K'),
]
MAKING_TYPES = [
    ('percent', 'Percent of metal value'),
    ('per_gram', 'Amount per gram'),
    ('fixed', 'Fixed amount'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_jewellery = fields.Boolean(string='Jewellery item')
    jewellery_category = fields.Selection(
        [('bangle', 'Bangle'), ('chain', 'Chain'), ('necklace', 'Necklace'), ('ring', 'Ring'),
         ('earrings', 'Earrings'), ('bracelet', 'Bracelet'), ('pendant', 'Pendant'),
         ('set', 'Set'), ('coin', 'Coin / bar')],
        string='Jewellery category', help='What kind of piece this design is; drives the icon and the filters.')
    jewellery_tryon_image = fields.Image(
        string='Try-on cutout', max_width=1024, max_height=1024,
        help='The design on a transparent background, for the kiosk to place on the client in the camera view.')
    jewellery_karat = fields.Selection(KARATS, string='Default karat')
    jewellery_wastage_pct = fields.Float(string='Default wastage %')
    jewellery_making_type = fields.Selection(
        MAKING_TYPES, string='Default making type', default='percent')
    jewellery_making_value = fields.Float(string='Default making value')
