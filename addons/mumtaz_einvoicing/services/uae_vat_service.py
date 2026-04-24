"""UAE FTA e-invoicing service.

Responsible for:
- TLV-encoded QR code generation per the UAE e-invoicing standard.
- TRN (Tax Registration Number) validation.
- QR image rendering (SVG placeholder; swap in qrcode library for production).
"""
import base64
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class UAEVATService:
    """Service class for UAE FTA e-invoicing operations."""

    def __init__(self, config):
        """
        Args:
            config: ``mumtaz.einvoice.config`` Odoo recordset for the company.
        """
        self.config = config

    # -------------------------------------------------------------------------
    # TLV helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _tlv_encode(tag: int, value: str) -> bytes:
        """Encode a single TLV field.

        Format: Tag (1 byte) + Length (1 byte) + Value (UTF-8 bytes).
        This matches the UAE FTA / ZATCA TLV specification.
        """
        value_bytes = value.encode('utf-8')
        length = len(value_bytes)
        if length > 255:
            raise ValueError(
                f'TLV field {tag} value is too long ({length} bytes, max 255).'
            )
        return bytes([tag, length]) + value_bytes

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def generate_qr_tlv(self, invoice) -> str:
        """Generate UAE FTA TLV-encoded QR string per the e-invoicing standard.

        TLV tags:
            1 – Seller name
            2 – VAT registration number (TRN)
            3 – Invoice timestamp (ISO 8601)
            4 – Invoice total (including VAT)
            5 – VAT amount

        Returns:
            Base64-encoded TLV string suitable for embedding in a QR code.
        """
        seller_name = invoice.company_id.name or ''
        trn = self.config.tax_registration_number or ''
        invoice_date = invoice.invoice_date or datetime.now().date()
        invoice_timestamp = invoice_date.isoformat() + 'T00:00:00Z'
        amount_total = str(round(float(invoice.amount_total), 2))
        amount_tax = str(round(float(invoice.amount_tax), 2))

        tlv = b''
        tlv += self._tlv_encode(1, seller_name)
        tlv += self._tlv_encode(2, trn)
        tlv += self._tlv_encode(3, invoice_timestamp)
        tlv += self._tlv_encode(4, amount_total)
        tlv += self._tlv_encode(5, amount_tax)

        encoded = base64.b64encode(tlv).decode('utf-8')
        _logger.debug('Generated UAE TLV QR for invoice %s: %s', invoice.name, encoded[:30])
        return encoded

    def validate_trn(self, trn: str) -> bool:
        """Validate UAE Tax Registration Number format.

        UAE TRN must be exactly 15 numeric digits.

        Args:
            trn: The TRN string to validate.

        Returns:
            True if valid, False otherwise.
        """
        return bool(trn and trn.isdigit() and len(trn) == 15)

    def generate_qr_image(self, qr_string: str) -> str:
        """Generate a QR code image from the TLV base64 string.

        Production recommendation: install the ``qrcode`` and ``Pillow`` Python
        packages and replace the SVG placeholder below with:

            import io, qrcode
            img = qrcode.make(qr_string)
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()

        For now, an inline SVG is returned so the module works without any
        additional dependencies.

        Args:
            qr_string: The base64 TLV string to encode in the QR image.

        Returns:
            Base64-encoded SVG (or PNG) string, suitable for storing in a
            Binary field rendered with ``widget="image"``.
        """
        # Attempt to use the qrcode library if available.
        try:
            import qrcode  # type: ignore[import]
            import io

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=2,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)

            try:
                from PIL import Image  # type: ignore[import]
                img = qr.make_image(fill_color='black', back_color='white')
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            except ImportError:
                _logger.debug('Pillow not available; falling back to SVG QR placeholder.')
        except ImportError:
            _logger.debug('qrcode library not available; using SVG QR placeholder.')

        # SVG placeholder — always works, no external dependencies.
        preview = qr_string[:20] if len(qr_string) > 20 else qr_string
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" '
            'viewBox="0 0 120 120">'
            '<rect width="120" height="120" fill="white" stroke="#ccc" stroke-width="1"/>'
            '<rect x="10" y="10" width="30" height="30" fill="none" stroke="black" stroke-width="3"/>'
            '<rect x="15" y="15" width="20" height="20" fill="black"/>'
            '<rect x="80" y="10" width="30" height="30" fill="none" stroke="black" stroke-width="3"/>'
            '<rect x="85" y="15" width="20" height="20" fill="black"/>'
            '<rect x="10" y="80" width="30" height="30" fill="none" stroke="black" stroke-width="3"/>'
            '<rect x="15" y="85" width="20" height="20" fill="black"/>'
            f'<text x="60" y="62" text-anchor="middle" font-size="5" font-family="monospace" fill="#333">'
            f'UAE QR</text>'
            f'<text x="60" y="72" text-anchor="middle" font-size="4" font-family="monospace" fill="#666">'
            f'{preview}</text>'
            '</svg>'
        )
        return base64.b64encode(svg.encode('utf-8')).decode('utf-8')

    # -------------------------------------------------------------------------
    # Decode helper (useful for debugging / auditing)
    # -------------------------------------------------------------------------
    def decode_qr_tlv(self, qr_string: str) -> dict:
        """Decode a UAE TLV QR string back into a dict.

        Args:
            qr_string: Base64-encoded TLV string.

        Returns:
            Dict with tag numbers as keys and decoded string values.
        """
        tag_names = {
            1: 'seller_name',
            2: 'tax_registration_number',
            3: 'invoice_timestamp',
            4: 'amount_total',
            5: 'amount_tax',
        }
        result = {}
        try:
            raw = base64.b64decode(qr_string)
            idx = 0
            while idx < len(raw):
                tag = raw[idx]
                length = raw[idx + 1]
                value = raw[idx + 2: idx + 2 + length].decode('utf-8')
                result[tag_names.get(tag, f'tag_{tag}')] = value
                idx += 2 + length
        except Exception as exc:
            _logger.warning('Failed to decode TLV QR string: %s', exc)
        return result
