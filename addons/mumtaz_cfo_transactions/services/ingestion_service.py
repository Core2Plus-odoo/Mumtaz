import base64
import csv
import hashlib
import io
import json
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError


class MumtazCFOIngestionService(models.AbstractModel):
    _name = "mumtaz.cfo.ingestion.service"
    _description = "Mumtaz CFO Ingestion Service"

    def process_upload_batch(self, batch):
        batch.ensure_one()
        rows, _headers = self._read_csv_rows(batch)

        mapping = self._resolve_mapping(batch)
        currency = batch.workspace_id.company_id.currency_id

        tx_count = 0
        dup_count = 0
        review_count = 0

        for row in rows:
            payload = self._normalize_row(row, mapping)
            source_hash = self._source_hash(batch, payload)

            is_dup = self.env["mumtaz.cfo.transaction"].search_count(
                [
                    ("workspace_id", "=", batch.workspace_id.id),
                    ("source_row_hash", "=", source_hash),
                ]
            ) > 0

            category = self._resolve_category(batch, payload)
            direction = "inflow" if payload["amount"] >= 0 else "outflow"
            entry_type = self._resolve_entry_type(payload, direction)

            requires_review, review_reason = self._review_flags(payload, is_dup)

            tx = self.env["mumtaz.cfo.transaction"].create(
                {
                    "workspace_id": batch.workspace_id.id,
                    "batch_id": batch.id,
                    "data_source_id": batch.data_source_id.id,
                    "date": payload["date"],
                    "description": payload["description"],
                    "reference": payload.get("reference"),
                    "amount": abs(payload["amount"]),
                    "currency_id": currency.id,
                    "direction": direction,
                    "entry_type": entry_type,
                    "category_id": category.id if category else False,
                    "source_row_hash": source_hash,
                    "raw_payload_json": json.dumps(row, ensure_ascii=False),
                    "is_duplicate": is_dup,
                    "requires_review": requires_review,
                    "review_reason": review_reason or False,
                }
            )
            tx_count += 1
            if is_dup:
                dup_count += 1
            if requires_review:
                review = self.env["mumtaz.cfo.review.item"].create(
                    {
                        "transaction_id": tx.id,
                        "reason": review_reason or "Needs review",
                    }
                )
                tx.review_item_id = review.id
                review_count += 1

        return {
            "transaction_count": tx_count,
            "duplicate_count": dup_count,
            "review_count": review_count,
        }

    def _resolve_mapping(self, batch):
        if batch.mapping_profile_id:
            return batch.mapping_profile_id.get_mapping_dict()
        return {"date": "date", "description": "description", "amount": "amount", "reference": "reference"}

    def _read_csv_rows(self, batch):
        if batch._detect_file_type(batch.upload_filename) != "csv":
            raise UserError("Phase 3 processing currently supports CSV files only.")

        payload = base64.b64decode(batch.upload_file or b"")
        if not payload:
            raise UserError("Upload file is empty.")

        decoded = None
        for enc in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                decoded = payload.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise UserError("Unable to decode CSV upload.")

        reader = csv.DictReader(io.StringIO(decoded))
        return list(reader), (reader.fieldnames or [])

    def _normalize_row(self, row, mapping):
        date_key = mapping.get("date", "date")
        desc_key = mapping.get("description", "description")
        amount_key = mapping.get("amount", "amount")
        ref_key = mapping.get("reference", "reference")

        raw_date = (row.get(date_key) or "").strip()
        raw_desc = (row.get(desc_key) or "").strip()
        raw_amount = (row.get(amount_key) or "0").replace(",", "").strip()
        raw_ref = (row.get(ref_key) or "").strip()

        if not raw_desc:
            raw_desc = "Unlabeled transaction"

        parsed_date = fields.Date.context_today(self)
        if raw_date:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    parsed_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue

        try:
            amount = float(raw_amount or 0.0)
        except ValueError:
            amount = 0.0

        return {
            "date": parsed_date,
            "description": raw_desc,
            "amount": amount,
            "reference": raw_ref,
        }

    def _source_hash(self, batch, payload):
        raw = "|".join(
            [
                str(batch.workspace_id.id),
                str(payload.get("date") or ""),
                str(payload.get("description") or ""),
                str(payload.get("amount") or 0),
                str(payload.get("reference") or ""),
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _resolve_entry_type(self, payload, direction):
        description = (payload.get("description") or "").lower()
        if "transfer" in description:
            return "transfer"
        if direction == "inflow":
            return "income"
        if direction == "outflow":
            return "expense"
        return "other"

    def _resolve_category(self, batch, payload):
        category_code = (payload.get("category_code") or "").strip().lower()
        if category_code:
            category = self.env["mumtaz.cfo.category"].search(
                [
                    ("workspace_id", "=", batch.workspace_id.id),
                    ("code", "=", category_code),
                ],
                limit=1,
            )
            if category:
                return category

        fallback_kind = "income" if payload.get("amount", 0) >= 0 else "expense"
        return self.env["mumtaz.cfo.category"].search(
            [
                ("workspace_id", "=", batch.workspace_id.id),
                ("kind", "=", fallback_kind),
            ],
            order="id asc",
            limit=1,
        )

    def _review_flags(self, payload, is_dup):
        if is_dup:
            return True, "Potential duplicate transaction"
        if abs(payload.get("amount", 0.0)) == 0.0:
            return True, "Zero-value transaction"
        if not payload.get("description"):
            return True, "Missing description"
        return False, False
