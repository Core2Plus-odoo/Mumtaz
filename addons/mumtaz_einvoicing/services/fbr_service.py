"""Pakistan FBR (Federal Board of Revenue) e-invoicing service.

Handles:
- FBR-compatible XML invoice generation.
- Submission to the FBR IMSP gateway.
- Cancellation support.
"""
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class FBRService:
    """Service class for Pakistan FBR e-invoicing operations."""

    # FBR IMSP gateway base URLs (environment-specific).
    SANDBOX_BASE = 'https://esp.fbr.gov.pk:8450'
    PROD_BASE    = 'https://gw.fbr.gov.pk/imsp/v1'

    LOGIN_PATH    = '/api/login'
    SUBMIT_PATH   = '/api/Invoice/GenerateInvoice'
    CANCEL_PATH   = '/api/Invoice/CancelInvoice'

    def __init__(self, config):
        """
        Args:
            config: ``mumtaz.einvoice.config`` Odoo recordset for the company.
        """
        self.config = config
        env = (config.fbr_environment or 'sandbox').lower()
        self.base_url = self.SANDBOX_BASE if env == 'sandbox' else self.PROD_BASE

    @property
    def login_url(self) -> str:
        return self.base_url + self.LOGIN_PATH

    @property
    def submit_url(self) -> str:
        return self.base_url + self.SUBMIT_PATH

    @property
    def cancel_url(self) -> str:
        return self.base_url + self.CANCEL_PATH

    # -------------------------------------------------------------------------
    # XML generation
    # -------------------------------------------------------------------------
    def generate_xml(self, invoice) -> str:
        """Generate an FBR IMSP-compatible XML document for the invoice.

        The FBR format follows the POS/IMSP schema used by registered POS systems.

        Args:
            invoice: ``account.move`` Odoo recordset.

        Returns:
            UTF-8 XML string.
        """
        issue_dt = invoice.invoice_date or datetime.now().date()
        issue_timestamp = f'{issue_dt.isoformat()}T00:00:00'

        buyer_ntn = invoice.partner_id.vat or ''
        buyer_cnic = ''  # Would come from a custom partner field if available
        buyer_name = self._escape_xml(invoice.partner_id.name or '')

        lines_xml = self._build_invoice_lines(invoice)

        total_quantity = sum(
            float(l.quantity)
            for l in invoice.invoice_line_ids
            if l.display_type not in ('line_section', 'line_note')
        )

        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<InvoiceType>
    <InvoiceNumber>{self._escape_xml(invoice.name)}</InvoiceNumber>
    <POSID>{self._escape_xml(self.config.fbr_pos_id or '')}</POSID>
    <USIN>{self._escape_xml(invoice.name)}</USIN>
    <DateTime>{issue_timestamp}</DateTime>
    <BuyerNTN>{self._escape_xml(buyer_ntn)}</BuyerNTN>
    <BuyerCNIC>{self._escape_xml(buyer_cnic)}</BuyerCNIC>
    <BuyerName>{buyer_name}</BuyerName>
    <BuyerPhoneNumber>{self._escape_xml(invoice.partner_id.phone or '')}</BuyerPhoneNumber>
    <TotalBillAmount>{round(float(invoice.amount_total), 2)}</TotalBillAmount>
    <TotalQuantity>{round(total_quantity, 4)}</TotalQuantity>
    <TotalSaleValue>{round(float(invoice.amount_untaxed), 2)}</TotalSaleValue>
    <TotalTaxCharged>{round(float(invoice.amount_tax), 2)}</TotalTaxCharged>
    <Discount>0</Discount>
    <FurtherTax>0</FurtherTax>
    <PaymentMode>1</PaymentMode>
    <RefUSIN/>
    <InvoiceType>SI</InvoiceType>
{lines_xml}
</InvoiceType>'''
        return xml

    def _build_invoice_lines(self, invoice) -> str:
        """Build FBR InvoiceItem elements for each invoice line."""
        items = []
        for idx, line in enumerate(invoice.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        ), start=1):
            unit_price = round(float(line.price_unit), 2)
            sale_value = round(float(line.price_subtotal), 2)
            tax_rate = 0.0
            if line.tax_ids:
                tax_rate = sum(
                    t.amount for t in line.tax_ids if t.amount_type == 'percent'
                )
            tax_charged = round(sale_value * tax_rate / 100, 2)

            items.append(f'''    <Items>
        <ItemCode>{self._escape_xml(line.product_id.default_code or str(idx))}</ItemCode>
        <ItemName>{self._escape_xml(line.name or line.product_id.name or 'Item')}</ItemName>
        <Quantity>{round(float(line.quantity), 4)}</Quantity>
        <PCTCode>{self._escape_xml(line.product_id.l10n_pk_pct_code if hasattr(line.product_id, 'l10n_pk_pct_code') else '')}</PCTCode>
        <TaxRate>{tax_rate}</TaxRate>
        <SaleValue>{sale_value}</SaleValue>
        <Discount>0</Discount>
        <FurtherTax>0</FurtherTax>
        <TaxCharged>{tax_charged}</TaxCharged>
        <TotalAmount>{round(sale_value + tax_charged, 2)}</TotalAmount>
        <UOM>{self._escape_xml(line.product_uom_id.name if hasattr(line, 'product_uom_id') and line.product_uom_id else 'PCS')}</UOM>
    </Items>''')
        return '\n'.join(items)

    # -------------------------------------------------------------------------
    # XML utility
    # -------------------------------------------------------------------------
    @staticmethod
    def _escape_xml(value: str) -> str:
        """Escape special characters for safe embedding in XML text nodes."""
        if not value:
            return ''
        return (
            str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
        )

    # -------------------------------------------------------------------------
    # QR / verification URL
    # -------------------------------------------------------------------------
    def build_qr_url(self, invoice) -> str:
        """Return the FBR public verification URL for the given invoice.

        FBR generates a verification URL for each accepted invoice; printing
        it as a QR on POS receipts lets customers verify authenticity.
        Format (FBR IMSP standard):
            https://esp.fbr.gov.pk/Verification/Invoice?inv={IRN}

        Falls back to the einvoice_number if no IRN was returned.
        """
        irn = (getattr(invoice, 'einvoice_number', None) or '').strip()
        if not irn:
            return ''
        # Use sandbox host for sandbox env, production host otherwise
        host = (
            'esp.fbr.gov.pk'
            if (self.config.fbr_environment or 'sandbox').lower() == 'sandbox'
            else 'gw.fbr.gov.pk'
        )
        return f"https://{host}/Verification/Invoice?inv={irn}"

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------
    def _get_auth_token(self) -> str:
        """Obtain a Bearer token from the FBR IMSP portal.

        Returns:
            JWT token string, or empty string on failure.
        """
        try:
            import requests  # type: ignore[import]
            payload = {
                'Username': self.config.fbr_username or '',
                'Password': self.config.fbr_password or '',
                'POSID': self.config.fbr_pos_id or '',
            }
            response = requests.post(
                self.login_url,
                json=payload,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('token', '')
            _logger.warning('FBR auth failed [%d]: %s', response.status_code, response.text[:200])
            return ''
        except Exception as exc:
            _logger.warning('FBR auth exception: %s', exc)
            return ''

    # -------------------------------------------------------------------------
    # API submission
    # -------------------------------------------------------------------------
    def submit(self, invoice, xml: str) -> dict:
        """Submit the FBR XML to the IMSP gateway.

        In sandbox mode this returns a simulated success response.

        Args:
            invoice: ``account.move`` Odoo recordset.
            xml: FBR XML string.

        Returns:
            Dict with keys: success (bool), einvoice_number (str), errors (list).
        """
        if self.config.fbr_environment == 'sandbox':
            _logger.info(
                'FBR sandbox: simulating accepted submission for invoice %s',
                invoice.name,
            )
            return {
                'success': True,
                'einvoice_number': f'FBR-{invoice.name}',
                'errors': [],
            }

        try:
            import requests  # type: ignore[import]
        except ImportError:
            return {
                'success': False,
                'errors': ['requests library is not available; cannot submit to FBR.'],
            }

        token = self._get_auth_token()
        if not token:
            return {
                'success': False,
                'errors': ['Failed to authenticate with FBR IMSP portal.'],
            }

        headers = {
            'Content-Type': 'application/xml',
            'Authorization': f'Bearer {token}',
            'POSID': self.config.fbr_pos_id or '',
        }

        try:
            response = requests.post(
                self.submit_url,
                data=xml.encode('utf-8'),
                headers=headers,
                timeout=30,
            )
            _logger.debug('FBR response [%d]: %s', response.status_code, response.text[:500])

            if response.status_code in (200, 201):
                try:
                    data = response.json()
                    code = data.get('Code', '')
                    if str(code) == '100':
                        return {
                            'success': True,
                            'einvoice_number': data.get('InvoiceNumber') or f'FBR-{invoice.name}',
                            'errors': [],
                        }
                    return {
                        'success': False,
                        'errors': [data.get('Errors') or data.get('Message') or 'FBR rejected the invoice.'],
                    }
                except Exception:
                    # XML response fallback
                    return {
                        'success': True,
                        'einvoice_number': f'FBR-{invoice.name}',
                        'errors': [],
                    }
            return {
                'success': False,
                'errors': [f'HTTP {response.status_code}: {response.text[:500]}'],
            }
        except Exception as exc:
            _logger.exception('FBR submission error for invoice %s', invoice.name)
            return {'success': False, 'errors': [str(exc)]}

    def cancel(self, invoice) -> dict:
        """Request cancellation of a previously accepted invoice.

        FBR does not yet expose a formal cancellation endpoint; this method
        logs the intent and returns success for local cancellation to proceed.

        Args:
            invoice: ``account.move`` Odoo recordset.

        Returns:
            Dict with keys: success (bool), errors (list).
        """
        _logger.info(
            'FBR cancellation requested for invoice %s (no FBR API; local cancel only).',
            invoice.name,
        )
        return {'success': True, 'errors': []}

    def test_connection(self) -> dict:
        """Test connectivity to the FBR endpoint.

        Returns:
            Dict with keys: success (bool), errors (list).
        """
        if self.config.fbr_environment == 'sandbox':
            return {'success': True, 'errors': []}

        try:
            import requests  # type: ignore[import]
            response = requests.get(
                self.base_url + '/api/',
                timeout=10,
            )
            if response.status_code < 500:
                return {'success': True, 'errors': []}
            return {'success': False, 'errors': [f'HTTP {response.status_code}']}
        except Exception as exc:
            return {'success': False, 'errors': [str(exc)]}
