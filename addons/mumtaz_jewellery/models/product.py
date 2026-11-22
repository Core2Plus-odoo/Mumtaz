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
    # Physical size, for the try-on to draw the piece at true scale and to
    # say where it sits or whether it fits. Set by the maker; nothing here
    # is estimated.
    jewellery_length_mm = fields.Float(
        string='Length (mm)', digits=(6, 0),
        help='Chains, necklaces, bracelets: the full length. Used by the try-on to say where it sits.')
    jewellery_inner_diameter_mm = fields.Float(
        string='Inner diameter (mm)', digits=(6, 1),
        help='Rings and bangles: the inner diameter. Used by the try-on to say whether it fits.')
    jewellery_width_mm = fields.Float(
        string='Width of the cutout (mm)', digits=(6, 0),
        help='How wide the try-on cutout is in real life, edge to edge, so the kiosk draws it at true size.')
    jewellery_karat = fields.Selection(KARATS, string='Default karat')
    jewellery_wastage_pct = fields.Float(string='Default wastage %')
    jewellery_making_type = fields.Selection(
        MAKING_TYPES, string='Default making type', default='percent')
    jewellery_making_value = fields.Float(string='Default making value')
