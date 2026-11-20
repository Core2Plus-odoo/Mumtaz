def migrate(cr, version):
    """Entries created before the kind tag existed: tag them from the records that point at them, so the accountant's
    Entries to Post queue is complete on an existing database."""
    cr.execute("""UPDATE account_move SET pharma_cod_kind = 'settlement' WHERE pharma_cod_kind IS NULL AND id IN (
                    SELECT move_id FROM pharma_courier_remittance WHERE move_id IS NOT NULL
                    UNION SELECT move_id FROM pharma_courier_remittance_prev_move_rel)""")
    cr.execute("""UPDATE account_move SET pharma_cod_kind = 'collection' WHERE pharma_cod_kind IS NULL AND id IN (
                    SELECT collection_move_id FROM pharma_courier_shipment WHERE collection_move_id IS NOT NULL
                    UNION SELECT move_id FROM pharma_courier_shipment_prev_move_rel)""")
    cr.execute("""UPDATE account_move r SET pharma_cod_kind = 'reversal' WHERE r.pharma_cod_kind IS NULL AND r.reversed_entry_id IN (
                    SELECT id FROM account_move WHERE pharma_cod_kind IN ('collection', 'settlement'))""")
