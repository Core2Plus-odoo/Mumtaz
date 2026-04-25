import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MumtazEInvoiceConfig(models.Model):
    """Per-company e-invoicing configuration.

    Stores credentials, environment settings, and preferences for each
    supported tax authority (UAE FTA, KSA ZATCA, Pakistan FBR).
    """

    _name = 'mumtaz.einvoice.config'
    _description = 'Mumtaz E-Invoice Configuration'
    _rec_name = 'company_id'

    # -------------------------------------------------------------------------
    # Core fields
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        ondelete='cascade',
        help='Company this configuration applies to.',
    )

    country_type = fields.Selection(
        selection=[
            ('uae', 'UAE FTA'),
            ('ksa', 'KSA ZATCA'),
            ('pakistan', 'Pakistan FBR'),
        ],
        string='Tax Authority',
        compute='_compute_country_type',
        store=True,
        help='Tax authority derived from the company country.',
    )

    tax_registration_number = fields.Char(
        string='Tax Registration Number',
        help='UAE TRN (15 digits) / KSA VAT number / Pakistan NTN.',
    )

    auto_submit = fields.Boolean(
        string='Auto-Submit on Post',
        default=False,
        help='Automatically submit e-invoices when invoices are confirmed (posted).',
    )

    sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='E-Invoice Sequence',
        help='Sequence used to generate e-invoice reference numbers.',
    )

    # -------------------------------------------------------------------------
    # KSA ZATCA fields
    # -------------------------------------------------------------------------
    zatca_environment = fields.Selection(
        selection=[
            ('sandbox',    'Sandbox (developer-portal)'),
            ('simulation', 'Simulation (mid-stage testing)'),
            ('production', 'Production (core)'),
        ],
        string='ZATCA Environment',
        default='sandbox',
        help='Sandbox for early dev, Simulation for end-to-end tests with '
             'ZATCA Phase 2 cleared invoices, Production for live submissions.',
    )

    zatca_vat_number = fields.Char(
        string='ZATCA VAT Number',
        help='15-digit Saudi VAT registration number (overrides company VAT '
             'for ZATCA submissions if both are set).',
    )

    zatca_certificate = fields.Text(
        string='ZATCA Certificate (Base64)',
        help='CSID certificate obtained from the ZATCA onboarding process. '
             'Stored as a base64-encoded PEM string.',
        groups='account.group_account_manager',
    )

    zatca_private_key = fields.Text(
        string='ZATCA Private Key (Base64)',
        help='Private key corresponding to the ZATCA certificate. '
             'Keep this value secret.',
        groups='account.group_account_manager',
    )

    zatca_compliance_request_id = fields.Char(
        string='ZATCA Compliance Request ID',
        help='Request ID returned by ZATCA during the compliance check phase.',
        readonly=True,
    )

    zatca_csr = fields.Text(
        string='ZATCA CSR (Base64)',
        help='Certificate Signing Request generated locally and submitted to ZATCA '
             'with an OTP to obtain the CSID.',
        groups='account.group_account_manager',
        readonly=True,
    )
    zatca_csid_secret = fields.Char(
        string='ZATCA CSID Secret',
        help='Secret returned alongside the binary security token after CSR submission.',
        groups='account.group_account_manager',
        readonly=True,
    )
    zatca_otp = fields.Char(
        string='ZATCA OTP (one-time)',
        help='Paste the OTP shown in the ZATCA fatoora portal here, then click '
             '"Submit CSR for CSID". The value is cleared after a successful exchange.',
    )

    # ── Identity fields used to build the CSR ────────────────────────────
    zatca_common_name = fields.Char(
        string='Common Name (CN)',
        help='Display name embedded in the CSR — typically the legal entity name.',
    )
    zatca_serial_number = fields.Char(
        string='Device Serial Number',
        help='Unique device identifier (e.g. POS terminal serial).',
    )
    zatca_organization = fields.Char(
        string='Organisation (O)',
        help='Legal entity name registered with ZATCA.',
    )
    zatca_org_unit = fields.Char(
        string='Organisational Unit (OU)',
        default='ZATCA',
    )

    # -------------------------------------------------------------------------
    # Pakistan FBR fields
    # -------------------------------------------------------------------------
    fbr_pos_id = fields.Char(
        string='FBR POS ID',
        help='Point-of-Sale ID assigned by the Pakistan Federal Board of Revenue.',
    )

    fbr_username = fields.Char(
        string='FBR Username',
        help='Username for the FBR integration portal.',
    )

    fbr_password = fields.Char(
        string='FBR Password',
        password=True,
        help='Password for the FBR integration portal.',
        groups='account.group_account_manager',
    )

    fbr_environment = fields.Selection(
        selection=[
            ('sandbox', 'Sandbox'),
            ('production', 'Production'),
        ],
        string='FBR Environment',
        default='sandbox',
    )

    # -------------------------------------------------------------------------
    # Computed fields
    # -------------------------------------------------------------------------
    @api.depends('company_id', 'company_id.country_id')
    def _compute_country_type(self):
        for config in self:
            code = (config.company_id.country_id.code or '').upper()
            if code == 'AE':
                config.country_type = 'uae'
            elif code == 'SA':
                config.country_type = 'ksa'
            elif code == 'PK':
                config.country_type = 'pakistan'
            else:
                config.country_type = False

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('company_id')
    def _check_unique_company(self):
        for config in self:
            domain = [
                ('company_id', '=', config.company_id.id),
                ('id', '!=', config.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    'An e-invoicing configuration already exists for company "%s". '
                    'Each company can have only one configuration.',
                    config.company_id.name,
                ))

    @api.constrains('tax_registration_number', 'country_type')
    def _check_trn_format(self):
        for config in self:
            trn = config.tax_registration_number
            if not trn:
                continue
            if config.country_type == 'uae':
                if not (trn.isdigit() and len(trn) == 15):
                    raise ValidationError(_(
                        'UAE Tax Registration Number must be exactly 15 digits. '
                        'Got: "%s" (%d characters).',
                        trn, len(trn),
                    ))

    # -------------------------------------------------------------------------
    # Default company helper
    # -------------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'company_id' in fields_list:
            defaults['company_id'] = self.env.company.id
        return defaults

    # -------------------------------------------------------------------------
    # ZATCA Phase 2 onboarding actions
    # -------------------------------------------------------------------------
    def action_generate_zatca_csr(self):
        """Generate an EC SECP256K1 keypair + CSR with ZATCA-specific OIDs.

        Stores the PEM private key in zatca_private_key and the base64-encoded
        CSR in zatca_csr. Caller then enters the ZATCA-issued OTP and clicks
        "Submit CSR for CSID".
        """
        self.ensure_one()
        if not self.zatca_vat_number and not self.tax_registration_number:
            raise UserError(_('Set the ZATCA VAT Number before generating a CSR.'))
        if not self.zatca_serial_number:
            raise UserError(_('Set the device Serial Number before generating a CSR.'))

        from ..services.zatca_service import ZATCAService
        svc = ZATCAService(self)
        try:
            result = svc.generate_keypair_and_csr(
                common_name        = self.zatca_common_name or self.company_id.name,
                vat_number         = self.zatca_vat_number or self.tax_registration_number,
                serial_number      = self.zatca_serial_number,
                organization       = self.zatca_organization or self.company_id.name,
                organizational_unit= self.zatca_org_unit or 'ZATCA',
            )
        except Exception as exc:
            _logger.exception('ZATCA CSR generation failed')
            raise UserError(_('Failed to generate CSR: %s') % str(exc))

        self.write({
            'zatca_private_key': result['private_key_pem'],
            'zatca_csr':         result['csr_base64'],
        })
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('ZATCA CSR Generated'),
                'message': _('Keypair + CSR created. Enter your OTP from the '
                             'ZATCA portal and click "Submit CSR for CSID".'),
                'type':    'success',
                'sticky':  False,
            },
        }

    def action_submit_zatca_csr(self):
        """Exchange the stored CSR + OTP for a CSID via ZATCA's compliance API."""
        self.ensure_one()
        if not self.zatca_csr:
            raise UserError(_('Generate a CSR first.'))
        if not self.zatca_otp:
            raise UserError(_('Paste the OTP from the ZATCA fatoora portal first.'))

        from ..services.zatca_service import ZATCAService
        svc = ZATCAService(self)
        try:
            data = svc.submit_csr_for_csid(
                csr_base64 = self.zatca_csr,
                otp        = self.zatca_otp,
            )
        except Exception as exc:
            _logger.exception('ZATCA CSR submission failed')
            raise UserError(_('CSR submission failed: %s') % str(exc))

        # Response carries: dispositionMessage, binarySecurityToken, secret, requestID
        self.write({
            'zatca_certificate':           data.get('binarySecurityToken') or '',
            'zatca_csid_secret':           data.get('secret') or '',
            'zatca_compliance_request_id': str(data.get('requestID') or ''),
            'zatca_otp':                   False,  # one-time, clear it
        })
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('ZATCA CSID Issued'),
                'message': data.get('dispositionMessage')
                            or _('Compliance CSID stored on this configuration.'),
                'type':    'success',
                'sticky':  True,
            },
        }

    # -------------------------------------------------------------------------
    # Test connection actions
    # -------------------------------------------------------------------------
    def action_test_zatca_connection(self):
        """Verify ZATCA sandbox connectivity."""
        self.ensure_one()
        from ..services.zatca_service import ZATCAService
        svc = ZATCAService(self)
        result = svc.test_connection()
        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('ZATCA Connection'),
                    'message': _('Connection to ZATCA %s successful.') % self.zatca_environment,
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('ZATCA Connection Failed'),
                'message': '\n'.join(result.get('errors', ['Unknown error'])),
                'type': 'danger',
                'sticky': True,
            },
        }

    def action_test_fbr_connection(self):
        """Verify FBR sandbox connectivity."""
        self.ensure_one()
        from ..services.fbr_service import FBRService
        svc = FBRService(self)
        result = svc.test_connection()
        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('FBR Connection'),
                    'message': _('Connection to FBR %s successful.') % self.fbr_environment,
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FBR Connection Failed'),
                'message': '\n'.join(result.get('errors', ['Unknown error'])),
                'type': 'danger',
                'sticky': True,
            },
        }
