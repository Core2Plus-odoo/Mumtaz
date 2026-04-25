import json
import logging
import uuid as uuid_lib
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extends account.move with e-invoicing fields and submission logic."""

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # Status & identification fields
    # -------------------------------------------------------------------------
    einvoice_status = fields.Selection(
        selection=[
            ('not_applicable', 'N/A'),
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='E-Invoice Status',
        default='not_applicable',
        copy=False,
        tracking=True,
        help='Current status of the e-invoice submission to the tax authority.',
    )

    einvoice_number = fields.Char(
        string='E-Invoice Number',
        copy=False,
        readonly=True,
        help='Government-assigned e-invoice reference number.',
    )

    einvoice_uuid = fields.Char(
        string='E-Invoice UUID',
        copy=False,
        readonly=True,
        help='Universally unique identifier used by ZATCA and other authorities.',
    )

    # -------------------------------------------------------------------------
    # QR code fields
    # -------------------------------------------------------------------------
    einvoice_qr_code = fields.Char(
        string='QR Code (TLV)',
        copy=False,
        readonly=True,
        help='TLV-encoded base64 QR string as per UAE/KSA e-invoicing standard.',
    )

    einvoice_qr_image = fields.Binary(
        string='QR Code Image',
        compute='_compute_einvoice_qr_image',
        store=True,
        attachment=True,
        help='Computed PNG/SVG QR code image for printing on the invoice.',
    )

    # -------------------------------------------------------------------------
    # Date/time tracking fields
    # -------------------------------------------------------------------------
    einvoice_submission_date = fields.Datetime(
        string='Submission Date',
        copy=False,
        readonly=True,
    )

    einvoice_acceptance_date = fields.Datetime(
        string='Acceptance Date',
        copy=False,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Payload & error fields
    # -------------------------------------------------------------------------
    einvoice_xml_payload = fields.Text(
        string='XML Payload',
        copy=False,
        readonly=True,
        help='The XML document sent to the tax authority.',
    )

    einvoice_validation_errors = fields.Text(
        string='Validation Errors',
        copy=False,
        readonly=True,
        help='JSON-encoded list of validation errors returned by the authority.',
    )

    # -------------------------------------------------------------------------
    # Country / authority type (computed)
    # -------------------------------------------------------------------------
    einvoice_country_type = fields.Selection(
        selection=[
            ('uae', 'UAE FTA'),
            ('ksa', 'KSA ZATCA'),
            ('pakistan', 'Pakistan FBR'),
        ],
        string='E-Invoice Authority',
        compute='_compute_einvoice_country_type',
        store=True,
        help='Tax authority determined from the company country.',
    )

    # -------------------------------------------------------------------------
    # Computed: country type
    # -------------------------------------------------------------------------
    @api.depends('company_id', 'company_id.country_id')
    def _compute_einvoice_country_type(self):
        for move in self:
            code = (move.company_id.country_id.code or '').upper()
            if code == 'AE':
                move.einvoice_country_type = 'uae'
            elif code == 'SA':
                move.einvoice_country_type = 'ksa'
            elif code == 'PK':
                move.einvoice_country_type = 'pakistan'
            else:
                move.einvoice_country_type = False

    # -------------------------------------------------------------------------
    # Computed: QR image from TLV string
    # -------------------------------------------------------------------------
    @api.depends('einvoice_qr_code')
    def _compute_einvoice_qr_image(self):
        for move in self:
            if move.einvoice_qr_code:
                config = move._get_einvoice_config()
                if config and move.einvoice_country_type in ('uae', 'ksa'):
                    from ..services.uae_vat_service import UAEVATService
                    svc = UAEVATService(config)
                    move.einvoice_qr_image = svc.generate_qr_image(move.einvoice_qr_code)
                else:
                    move.einvoice_qr_image = False
            else:
                move.einvoice_qr_image = False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_einvoice_config(self):
        """Return the mumtaz.einvoice.config record for the current company, or False."""
        self.ensure_one()
        config = self.env['mumtaz.einvoice.config'].search(
            [('company_id', '=', self.company_id.id)], limit=1
        )
        return config or False

    def _ensure_uuid(self):
        """Ensure the invoice has a UUID, generating one if needed."""
        self.ensure_one()
        if not self.einvoice_uuid:
            self.einvoice_uuid = str(uuid_lib.uuid4())

    # -------------------------------------------------------------------------
    # Smart button count helper
    # -------------------------------------------------------------------------
    def _get_einvoice_smart_button_data(self):
        """Return label and icon for the smart button."""
        self.ensure_one()
        status_labels = {
            'not_applicable': ('N/A', 'fa-ban'),
            'draft': ('E-Invoice Draft', 'fa-file-text-o'),
            'submitted': ('Submitted', 'fa-paper-plane'),
            'accepted': ('Accepted', 'fa-check-circle'),
            'rejected': ('Rejected', 'fa-times-circle'),
            'cancelled': ('Cancelled', 'fa-trash'),
        }
        label, icon = status_labels.get(self.einvoice_status, ('E-Invoice', 'fa-file-text-o'))
        return label, icon

    # -------------------------------------------------------------------------
    # Main submit action
    # -------------------------------------------------------------------------
    def action_submit_einvoice(self):
        """Route to the correct service based on einvoice_country_type and submit."""
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                raise UserError(_('E-invoicing is only supported for customer invoices and credit notes.'))

            if move.state != 'posted':
                raise UserError(_('Only posted (confirmed) invoices can be submitted for e-invoicing.'))

            if move.einvoice_status in ('submitted', 'accepted'):
                raise UserError(_(
                    'Invoice %s has already been submitted. Cancel it first to resubmit.',
                    move.name,
                ))

            config = move._get_einvoice_config()
            if not config:
                raise UserError(_(
                    'No e-invoicing configuration found for company "%s". '
                    'Please configure it under E-Invoicing > Configuration.',
                    move.company_id.name,
                ))

            country_type = move.einvoice_country_type
            if not country_type:
                raise UserError(_(
                    'The company country (%s) is not supported for e-invoicing. '
                    'Supported countries: UAE, Saudi Arabia, Pakistan.',
                    move.company_id.country_id.name or 'Unknown',
                ))

            move._ensure_uuid()

            if country_type == 'uae':
                move._submit_uae(config)
            elif country_type == 'ksa':
                move._submit_ksa(config)
            elif country_type == 'pakistan':
                move._submit_pakistan(config)

        return True

    # -------------------------------------------------------------------------
    # UAE FTA submission
    # -------------------------------------------------------------------------
    def _submit_uae(self, config):
        """Generate UAE QR and mark the invoice as accepted (FTA is QR-only, no API)."""
        self.ensure_one()
        from ..services.uae_vat_service import UAEVATService

        svc = UAEVATService(config)

        if not svc.validate_trn(config.tax_registration_number):
            raise ValidationError(_(
                'Invalid UAE Tax Registration Number (TRN). '
                'TRN must be exactly 15 digits. Current value: "%s".',
                config.tax_registration_number or '',
            ))

        try:
            qr_string = svc.generate_qr_tlv(self)
        except Exception as exc:
            _logger.exception('UAE QR generation failed for invoice %s', self.name)
            self.write({
                'einvoice_status': 'rejected',
                'einvoice_validation_errors': json.dumps([str(exc)]),
            })
            raise UserError(_('UAE QR generation failed: %s') % str(exc))

        now = datetime.now()
        seq = config.sequence_id
        einvoice_number = seq.next_by_id() if seq else self.env['ir.sequence'].next_by_code('mumtaz.einvoice')

        self.write({
            'einvoice_status': 'accepted',
            'einvoice_qr_code': qr_string,
            'einvoice_number': einvoice_number or f'UAE-{self.name}',
            'einvoice_submission_date': now,
            'einvoice_acceptance_date': now,
            'einvoice_validation_errors': False,
        })
        _logger.info('UAE e-invoice accepted for %s (TRN: %s)', self.name, config.tax_registration_number)

    # -------------------------------------------------------------------------
    # KSA ZATCA submission
    # -------------------------------------------------------------------------
    def _submit_ksa(self, config):
        """Generate ZATCA UBL XML, submit to API, handle response."""
        self.ensure_one()
        from ..services.zatca_service import ZATCAService

        svc = ZATCAService(config)

        try:
            xml = svc.generate_xml(self)
        except Exception as exc:
            _logger.exception('ZATCA XML generation failed for invoice %s', self.name)
            raise UserError(_('ZATCA XML generation failed: %s') % str(exc))

        now = datetime.now()
        self.write({
            'einvoice_status': 'submitted',
            'einvoice_xml_payload': xml,
            'einvoice_submission_date': now,
        })

        try:
            result = svc.submit(self, xml)
        except Exception as exc:
            _logger.exception('ZATCA submission failed for invoice %s', self.name)
            self.write({
                'einvoice_status': 'rejected',
                'einvoice_validation_errors': json.dumps([str(exc)]),
            })
            raise UserError(_('ZATCA submission failed: %s') % str(exc))

        if result.get('success'):
            # Generate the ZATCA QR (TLV-encoded base64) for printing
            try:
                qr_string = svc.build_qr(self)
            except Exception:
                _logger.exception('ZATCA QR generation failed for %s', self.name)
                qr_string = False

            self.write({
                'einvoice_status': 'accepted',
                'einvoice_number': result.get('einvoice_number') or f'ZATCA-{self.name}',
                'einvoice_acceptance_date': datetime.now(),
                'einvoice_qr_code': qr_string or False,
                'einvoice_validation_errors': False,
            })
            _logger.info('ZATCA invoice accepted for %s', self.name)
        else:
            errors = result.get('errors', [])
            self.write({
                'einvoice_status': 'rejected',
                'einvoice_validation_errors': json.dumps(errors),
            })
            raise UserError(_(
                'ZATCA rejected the invoice "%s":\n%s',
                self.name,
                '\n'.join(str(e) for e in errors),
            ))

    # -------------------------------------------------------------------------
    # Pakistan FBR submission
    # -------------------------------------------------------------------------
    def _submit_pakistan(self, config):
        """Generate FBR XML, submit to API, handle response."""
        self.ensure_one()
        from ..services.fbr_service import FBRService

        svc = FBRService(config)

        try:
            xml = svc.generate_xml(self)
        except Exception as exc:
            _logger.exception('FBR XML generation failed for invoice %s', self.name)
            raise UserError(_('FBR XML generation failed: %s') % str(exc))

        now = datetime.now()
        self.write({
            'einvoice_status': 'submitted',
            'einvoice_xml_payload': xml,
            'einvoice_submission_date': now,
        })

        try:
            result = svc.submit(self, xml)
        except Exception as exc:
            _logger.exception('FBR submission failed for invoice %s', self.name)
            self.write({
                'einvoice_status': 'rejected',
                'einvoice_validation_errors': json.dumps([str(exc)]),
            })
            raise UserError(_('FBR submission failed: %s') % str(exc))

        if result.get('success'):
            self.write({
                'einvoice_status': 'accepted',
                'einvoice_number': result.get('einvoice_number') or f'FBR-{self.name}',
                'einvoice_acceptance_date': datetime.now(),
                'einvoice_validation_errors': False,
            })
            _logger.info('FBR invoice accepted for %s', self.name)
        else:
            errors = result.get('errors', [])
            self.write({
                'einvoice_status': 'rejected',
                'einvoice_validation_errors': json.dumps(errors),
            })
            raise UserError(_(
                'FBR rejected the invoice "%s":\n%s',
                self.name,
                '\n'.join(str(e) for e in errors),
            ))

    # -------------------------------------------------------------------------
    # Cancel action
    # -------------------------------------------------------------------------
    def action_cancel_einvoice(self):
        """Mark as cancelled; call authority cancellation endpoint if previously accepted."""
        for move in self:
            if move.einvoice_status == 'not_applicable':
                raise UserError(_('This invoice does not have an active e-invoice submission.'))

            if move.einvoice_status == 'cancelled':
                raise UserError(_('Invoice %s is already cancelled.') % move.name)

            previously_accepted = move.einvoice_status == 'accepted'
            config = move._get_einvoice_config()

            if previously_accepted and config:
                country_type = move.einvoice_country_type
                try:
                    if country_type == 'ksa':
                        from ..services.zatca_service import ZATCAService
                        svc = ZATCAService(config)
                        svc.cancel(move)
                    elif country_type == 'pakistan':
                        from ..services.fbr_service import FBRService
                        svc = FBRService(config)
                        svc.cancel(move)
                    # UAE FTA: no cancellation API; local cancel is sufficient
                except Exception as exc:
                    _logger.warning(
                        'Cancellation API call failed for invoice %s: %s',
                        move.name, exc,
                    )
                    # We still proceed with local cancellation

            move.write({'einvoice_status': 'cancelled'})
            _logger.info('E-invoice cancelled for %s', move.name)

        return True

    # -------------------------------------------------------------------------
    # Auto-submit on post (if configured)
    # -------------------------------------------------------------------------
    def action_post(self):
        """Override to auto-submit when the company config has auto_submit=True."""
        result = super().action_post()
        for move in self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
                      and m.einvoice_country_type
        ):
            config = move._get_einvoice_config()
            if config and config.auto_submit:
                try:
                    move.action_submit_einvoice()
                except Exception as exc:
                    _logger.warning(
                        'Auto e-invoice submission failed for %s: %s',
                        move.name, exc,
                    )
                    # Do not block the post; just log and move on.
        return result
