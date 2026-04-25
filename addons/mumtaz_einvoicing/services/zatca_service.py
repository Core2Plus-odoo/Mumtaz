"""KSA ZATCA Phase 2 e-invoicing service.

Handles:
- UBL 2.1 XML invoice generation compliant with ZATCA specs.
- Signing placeholder (full signing requires a ZATCA-issued certificate).
- Submission to ZATCA sandbox / production APIs.
- Cancellation of previously accepted invoices.
"""
import base64
import hashlib
import json
import logging
import uuid as uuid_lib
from datetime import datetime

_logger = logging.getLogger(__name__)


class ZATCAService:
    """Service class for KSA ZATCA Phase 2 e-invoicing operations."""

    # Correct ZATCA gateway is gw-fatoora (singular, no 'h').
    SANDBOX_URL    = 'https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal'
    SIMULATION_URL = 'https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation'
    PROD_URL       = 'https://gw-fatoora.zatca.gov.sa/e-invoicing/core'

    def __init__(self, config):
        """
        Args:
            config: ``mumtaz.einvoice.config`` Odoo recordset for the company.
        """
        self.config = config
        env = (config.zatca_environment or 'sandbox').lower()
        self.base_url = {
            'sandbox':    self.SANDBOX_URL,
            'simulation': self.SIMULATION_URL,
            'production': self.PROD_URL,
        }.get(env, self.SANDBOX_URL)

    # -------------------------------------------------------------------------
    # XML generation
    # -------------------------------------------------------------------------
    def generate_xml(self, invoice) -> str:
        """Generate a ZATCA-compliant UBL 2.1 XML document for the invoice.

        This covers the mandatory fields required by ZATCA Phase 2 for
        standard tax invoices (Type 388) and simplified credit notes (Type 389).

        Args:
            invoice: ``account.move`` Odoo recordset.

        Returns:
            UTF-8 XML string.
        """
        invoice_uuid = invoice.einvoice_uuid or str(uuid_lib.uuid4())
        issue_date = invoice.invoice_date or datetime.now().date()
        issue_time = '00:00:00'
        invoice_type_code = 389 if invoice.move_type == 'out_refund' else 388

        # Build invoice lines
        lines_xml = self._build_invoice_lines(invoice)

        # Build tax totals
        tax_total_xml = self._build_tax_total(invoice)

        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionURI>urn:oasis:names:specification:ubl:dsig:ext:DSCF</ext:ExtensionURI>
            <ext:ExtensionContent/>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
    <cbc:ID>{self._escape_xml(invoice.name)}</cbc:ID>
    <cbc:UUID>{invoice_uuid}</cbc:UUID>
    <cbc:IssueDate>{issue_date.isoformat()}</cbc:IssueDate>
    <cbc:IssueTime>{issue_time}</cbc:IssueTime>
    <cbc:InvoiceTypeCode name="0200000">{invoice_type_code}</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>{self._escape_xml(invoice.currency_id.name)}</cbc:DocumentCurrencyCode>
    <cbc:TaxCurrencyCode>SAR</cbc:TaxCurrencyCode>
    <cac:AdditionalDocumentReference>
        <cbc:ID>ICV</cbc:ID>
        <cbc:UUID>{self._get_icv(invoice)}</cbc:UUID>
    </cac:AdditionalDocumentReference>
    <cac:AdditionalDocumentReference>
        <cbc:ID>PIH</cbc:ID>
        <cac:Attachment>
            <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">
                {self._get_pih_hash(invoice)}
            </cbc:EmbeddedDocumentBinaryObject>
        </cac:Attachment>
    </cac:AdditionalDocumentReference>
    <cac:AdditionalDocumentReference>
        <cbc:ID>QR</cbc:ID>
        <cac:Attachment>
            <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">{self.build_qr(invoice)}</cbc:EmbeddedDocumentBinaryObject>
        </cac:Attachment>
    </cac:AdditionalDocumentReference>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="CRN">{self._escape_xml(invoice.company_id.company_registry or '')}</cbc:ID>
            </cac:PartyIdentification>
            <cac:PostalAddress>
                <cbc:StreetName>{self._escape_xml(invoice.company_id.street or '')}</cbc:StreetName>
                <cbc:BuildingNumber>{self._escape_xml(invoice.company_id.street2 or '0000')}</cbc:BuildingNumber>
                <cbc:CityName>{self._escape_xml(invoice.company_id.city or '')}</cbc:CityName>
                <cbc:PostalZone>{self._escape_xml(invoice.company_id.zip or '00000')}</cbc:PostalZone>
                <cbc:CountrySubentity>{self._escape_xml(invoice.company_id.state_id.name or '')}</cbc:CountrySubentity>
                <cac:Country>
                    <cbc:IdentificationCode>SA</cbc:IdentificationCode>
                </cac:Country>
            </cac:PostalAddress>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>{self._escape_xml(self.config.tax_registration_number or '')}</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID>VAT</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>{self._escape_xml(invoice.company_id.name)}</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PostalAddress>
                <cbc:StreetName>{self._escape_xml(invoice.partner_id.street or '')}</cbc:StreetName>
                <cbc:CityName>{self._escape_xml(invoice.partner_id.city or '')}</cbc:CityName>
                <cac:Country>
                    <cbc:IdentificationCode>{self._escape_xml(invoice.partner_id.country_id.code or 'SA')}</cbc:IdentificationCode>
                </cac:Country>
            </cac:PostalAddress>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>{self._escape_xml(invoice.partner_id.vat or '')}</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID>VAT</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>{self._escape_xml(invoice.partner_id.name or '')}</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:PaymentMeans>
        <cbc:PaymentMeansCode>10</cbc:PaymentMeansCode>
    </cac:PaymentMeans>
{tax_total_xml}
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{round(float(invoice.amount_untaxed), 2)}</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{round(float(invoice.amount_untaxed), 2)}</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{round(float(invoice.amount_total), 2)}</cbc:TaxInclusiveAmount>
        <cbc:AllowanceTotalAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">0.00</cbc:AllowanceTotalAmount>
        <cbc:PrepaidAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">0.00</cbc:PrepaidAmount>
        <cbc:PayableAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{round(float(invoice.amount_total), 2)}</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
{lines_xml}
</Invoice>'''
        return xml

    def _get_icv(self, invoice) -> str:
        """Return a sequential invoice counter value (ICV) for ZATCA."""
        # In production this should come from a persistent counter.
        # For now we derive a stable integer from the invoice ID.
        return str(invoice.id or 1)

    def _get_pih_hash(self, invoice) -> str:
        """Return Previous Invoice Hash (PIH) — NeshanHash of the prior invoice XML.

        For the first invoice in a chain, ZATCA specifies a static seed value.
        """
        # Placeholder: real implementation requires storing the hash of the
        # previously submitted invoice per company.
        seed = 'NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjZmQ4NWI0MGQyMjFiNGFiMzQ1YjkzNTQ1MjZiZjNjOTQ1MDJiNGQ='
        return seed

    def _build_invoice_lines(self, invoice) -> str:
        """Build UBL InvoiceLine elements for each invoice line."""
        lines = []
        for idx, line in enumerate(invoice.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        ), start=1):
            unit_price = round(float(line.price_unit), 2)
            line_total = round(float(line.price_subtotal), 2)
            tax_amount = round(float(line.price_total - line.price_subtotal), 2)
            tax_percent = 0.0
            if line.tax_ids:
                tax_percent = sum(t.amount for t in line.tax_ids if t.amount_type == 'percent')

            lines.append(f'''    <cac:InvoiceLine>
        <cbc:ID>{idx}</cbc:ID>
        <cbc:InvoicedQuantity unitCode="PCE">{round(float(line.quantity), 4)}</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{line_total}</cbc:LineExtensionAmount>
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{tax_amount}</cbc:TaxAmount>
            <cbc:RoundingAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{round(line_total + tax_amount, 2)}</cbc:RoundingAmount>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Name>{self._escape_xml(line.name or line.product_id.name or 'Item')}</cbc:Name>
            <cac:ClassifiedTaxCategory>
                <cbc:ID>S</cbc:ID>
                <cbc:Percent>{tax_percent}</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:ClassifiedTaxCategory>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount currencyID="{self._escape_xml(invoice.currency_id.name)}">{unit_price}</cbc:PriceAmount>
            <cbc:BaseQuantity unitCode="PCE">1</cbc:BaseQuantity>
            <cac:AllowanceCharge>
                <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
                <cbc:AllowanceChargeReason>discount</cbc:AllowanceChargeReason>
                <cbc:Amount currencyID="{self._escape_xml(invoice.currency_id.name)}">0.00</cbc:Amount>
            </cac:AllowanceCharge>
        </cac:Price>
    </cac:InvoiceLine>''')
        return '\n'.join(lines)

    def _build_tax_total(self, invoice) -> str:
        """Build UBL TaxTotal element."""
        tax_amount = round(float(invoice.amount_tax), 2)
        currency = self._escape_xml(invoice.currency_id.name)

        # Collect tax subtotals per rate
        tax_subtotals = {}
        for line in invoice.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        ):
            for tax in line.tax_ids:
                if tax.amount_type == 'percent':
                    rate = tax.amount
                    if rate not in tax_subtotals:
                        tax_subtotals[rate] = {'taxable': 0.0, 'tax': 0.0}
                    tax_subtotals[rate]['taxable'] += float(line.price_subtotal)
                    tax_subtotals[rate]['tax'] += float(line.price_subtotal * rate / 100)

        subtotals_xml = ''
        for rate, amounts in tax_subtotals.items():
            subtotals_xml += f'''        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="{currency}">{round(amounts['taxable'], 2)}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="{currency}">{round(amounts['tax'], 2)}</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID>S</cbc:ID>
                <cbc:Percent>{rate}</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
'''

        if not subtotals_xml:
            # Fallback if no tax lines
            subtotals_xml = f'''        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="{currency}">{round(float(invoice.amount_untaxed), 2)}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="{currency}">{tax_amount}</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID>S</cbc:ID>
                <cbc:Percent>15</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
'''

        return f'''    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="{currency}">{tax_amount}</cbc:TaxAmount>
{subtotals_xml}    </cac:TaxTotal>'''

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
    # QR code (TLV-encoded base64) — ZATCA Phase 1 spec
    # -------------------------------------------------------------------------
    @staticmethod
    def _tlv(tag: int, value) -> bytes:
        """Encode a single Tag-Length-Value tuple per ZATCA QR spec."""
        if isinstance(value, str):
            value = value.encode('utf-8')
        if len(value) > 255:
            raise ValueError(f"TLV value too long for tag {tag}: {len(value)} bytes")
        return bytes([tag, len(value)]) + value

    def build_qr(self, invoice) -> str:
        """Return a base64 TLV string suitable for a ZATCA QR code.

        Tags (per ZATCA Phase 1 spec):
          1 = seller name
          2 = VAT registration number
          3 = invoice timestamp (ISO 8601 UTC)
          4 = invoice total (with VAT)
          5 = VAT amount
        Phase 2 adds 6 (XML hash), 7 (digital signature), 8 (public key).
        """
        seller_name = self.config.company_id.name or ''
        vat_number  = self.config.zatca_vat_number or self.config.company_id.vat or ''

        ts = invoice.invoice_date or datetime.now().date()
        # Compose ISO 8601 UTC timestamp; ZATCA accepts either date+time or full ISO.
        if hasattr(ts, 'isoformat'):
            timestamp = f"{ts.isoformat()}T00:00:00Z"
        else:
            timestamp = str(ts)

        total = f"{invoice.amount_total:.2f}" if invoice.amount_total is not None else '0.00'
        vat   = f"{invoice.amount_tax:.2f}"   if invoice.amount_tax   is not None else '0.00'

        payload = (
            self._tlv(1, seller_name) +
            self._tlv(2, vat_number)  +
            self._tlv(3, timestamp)   +
            self._tlv(4, total)       +
            self._tlv(5, vat)
        )
        return base64.b64encode(payload).decode('ascii')

    # -------------------------------------------------------------------------
    # Phase 2 onboarding — CSR generation + submission
    # -------------------------------------------------------------------------
    def generate_keypair_and_csr(self, *, common_name, vat_number,
                                 serial_number, organization,
                                 organizational_unit='ZATCA',
                                 country='SA') -> dict:
        """Generate an EC SECP256K1 keypair + CSR with ZATCA-specific OIDs.

        Returns a dict with:
          - private_key_pem  PEM-encoded private key (string)
          - csr_pem          PEM-encoded CSR (string)
          - csr_base64       base64 of the PEM CSR — what ZATCA's API expects
        """
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = ec.generate_private_key(ec.SECP256K1())

        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME,              common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME,        organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organizational_unit),
            x509.NameAttribute(NameOID.COUNTRY_NAME,             country),
        ])

        builder = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(subject)
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DirectoryName(x509.Name([
                        # ZATCA-specific OIDs in the SAN DirectoryName
                        x509.NameAttribute(x509.ObjectIdentifier("2.5.4.4"),                 serial_number),  # SN
                        x509.NameAttribute(x509.ObjectIdentifier("0.9.2342.19200300.100.1.1"), vat_number),    # UID
                        x509.NameAttribute(x509.ObjectIdentifier("2.5.4.12"),                "1100"),         # title — invoice types
                        x509.NameAttribute(x509.ObjectIdentifier("2.5.4.26"),                "Saudi Arabia"), # registered address
                        x509.NameAttribute(x509.ObjectIdentifier("2.5.4.15"),                organization),   # business category
                    ]))
                ]),
                critical=False,
            )
        )
        csr = builder.sign(key, hashes.SHA256())

        pem_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pem_csr = csr.public_bytes(serialization.Encoding.PEM)

        return {
            'private_key_pem': pem_key.decode('ascii'),
            'csr_pem':         pem_csr.decode('ascii'),
            'csr_base64':      base64.b64encode(pem_csr).decode('ascii'),
        }

    def submit_csr_for_csid(self, *, csr_base64: str, otp: str) -> dict:
        """Exchange a CSR + OTP for a Compliance CSID via the ZATCA onboarding API.

        Returns the parsed JSON response, which contains:
          - dispositionMessage
          - binarySecurityToken (the CSID — store as zatca_certificate)
          - secret
          - requestID
        """
        try:
            import requests  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("'requests' not installed — cannot reach ZATCA.") from exc

        url = self.base_url + '/compliance'
        response = requests.post(
            url,
            headers={
                'Accept':         'application/json',
                'Accept-Version': 'V2',
                'OTP':            otp,
                'Content-Type':   'application/json',
            },
            json={'csr': csr_base64},
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"ZATCA onboarding failed: HTTP {response.status_code} — "
                f"{response.text[:300]}"
            )
        return response.json()

    # -------------------------------------------------------------------------
    # Hash / signing helpers
    # -------------------------------------------------------------------------
    def _hash_xml(self, xml: str) -> str:
        """Return SHA-256 hash of the XML document (base64-encoded)."""
        digest = hashlib.sha256(xml.encode('utf-8')).digest()
        return base64.b64encode(digest).decode('utf-8')

    # -------------------------------------------------------------------------
    # API submission
    # -------------------------------------------------------------------------
    def submit(self, invoice, xml: str) -> dict:
        """Submit the UBL XML to the ZATCA API.

        In sandbox mode this method returns a simulated success response so
        that development can proceed without a real ZATCA certificate.

        Args:
            invoice: ``account.move`` Odoo recordset.
            xml: UBL 2.1 XML string.

        Returns:
            Dict with keys: success (bool), einvoice_number (str), errors (list).
        """
        if self.config.zatca_environment == 'sandbox':
            _logger.info(
                'ZATCA sandbox: simulating accepted submission for invoice %s',
                invoice.name,
            )
            return {
                'success': True,
                'einvoice_number': f'ZATCA-{invoice.name}',
                'errors': [],
            }

        try:
            import requests  # type: ignore[import]
        except ImportError:
            return {
                'success': False,
                'errors': ['requests library is not available; cannot submit to ZATCA.'],
            }

        xml_b64 = base64.b64encode(xml.encode('utf-8')).decode('utf-8')
        xml_hash = self._hash_xml(xml)

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Version': 'V2',
        }

        # Attach certificate if configured
        if self.config.zatca_certificate:
            headers['Authorization'] = (
                'Basic ' + base64.b64encode(
                    f'{self.config.zatca_certificate}:{self.config.zatca_private_key or ""}'.encode()
                ).decode()
            )

        payload = {
            'invoiceHash': xml_hash,
            'uuid': invoice.einvoice_uuid,
            'invoice': xml_b64,
        }

        try:
            response = requests.post(
                f'{self.base_url}/invoices/reporting/single',
                json=payload,
                headers=headers,
                timeout=30,
            )
            _logger.debug('ZATCA response [%d]: %s', response.status_code, response.text[:500])

            if response.status_code in (200, 202):
                data = response.json()
                return {
                    'success': True,
                    'einvoice_number': data.get('reportingStatus') or data.get('clearanceStatus') or f'ZATCA-{invoice.name}',
                    'errors': data.get('validationResults', {}).get('errorMessages', []),
                }
            return {
                'success': False,
                'errors': [f'HTTP {response.status_code}: {response.text[:500]}'],
            }
        except Exception as exc:
            _logger.exception('ZATCA submission error for invoice %s', invoice.name)
            return {'success': False, 'errors': [str(exc)]}

    def cancel(self, invoice) -> dict:
        """Request cancellation of a previously accepted invoice from ZATCA.

        Args:
            invoice: ``account.move`` Odoo recordset.

        Returns:
            Dict with keys: success (bool), errors (list).
        """
        if self.config.zatca_environment == 'sandbox':
            _logger.info('ZATCA sandbox: simulating cancellation for invoice %s', invoice.name)
            return {'success': True, 'errors': []}

        try:
            import requests  # type: ignore[import]
        except ImportError:
            return {'success': False, 'errors': ['requests library not available.']}

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Version': 'V2',
        }
        payload = {
            'uuid': invoice.einvoice_uuid,
            'reason': 'Invoice cancelled by user.',
        }
        try:
            response = requests.delete(
                f'{self.base_url}/invoices/{invoice.einvoice_uuid}',
                json=payload,
                headers=headers,
                timeout=30,
            )
            if response.status_code in (200, 202, 204):
                return {'success': True, 'errors': []}
            return {
                'success': False,
                'errors': [f'HTTP {response.status_code}: {response.text[:500]}'],
            }
        except Exception as exc:
            return {'success': False, 'errors': [str(exc)]}

    def test_connection(self) -> dict:
        """Test connectivity to the ZATCA endpoint.

        Returns:
            Dict with keys: success (bool), errors (list).
        """
        if self.config.zatca_environment == 'sandbox':
            return {'success': True, 'errors': []}

        try:
            import requests  # type: ignore[import]
            response = requests.get(self.base_url, timeout=10)
            if response.status_code < 500:
                return {'success': True, 'errors': []}
            return {'success': False, 'errors': [f'HTTP {response.status_code}']}
        except Exception as exc:
            return {'success': False, 'errors': [str(exc)]}
