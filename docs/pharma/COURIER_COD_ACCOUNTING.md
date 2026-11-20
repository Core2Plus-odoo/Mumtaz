# Courier COD accounting (`pharma_courier_cod_accounting`, slices 1b and 1c)

Two actions, both producing **draft** miscellaneous journal entries. Nothing is posted for you: the accountant reviews and posts in Accounting.

1. **Create collection entry** on a delivered COD shipment (slice 1c): the courier collected the customer's cash.
2. **Create journal entry** on a **reconciled** remittance (slice 1b): the courier remitted it, less deductions.

Together they make the clearing account mean something: collections debit it, settlements credit it, and its balance is **what the couriers still hold**.

## Collection entry (per shipment, from the shipment form or the list Action menu)

For a shipment with 1,000 collected:

| Account | Debit | Credit |
| --- | ---: | ---: |
| **COD clearing account** (courier holds the cash) | 1,000 | |
| Customer receivable, customer set on the line | | 1,000 |

The receivable credit carries the customer, so in Accounting it is matched to the customer invoice with the standard
reconciliation screen. The amount is what the courier **collected**, not what was declared. It needs a delivered COD
shipment with collected money and a matching sale order (that is where the customer comes from). Several shipments can be selected
in the list; it is all or nothing, and the error names each shipment that cannot have one. Returned parcels are refused: a
return with COD collected is an exception for Finance to settle, not a collection to book. One entry per shipment; a cancelled or
deleted draft can be recreated.

## What the entry books

For a slip with gross 1,000, freight 100, COD fee 20, withholding sales tax 10, and 870 received at the bank:

| Account (set per courier) | Debit | Credit |
| --- | ---: | ---: |
| Bank / receipts account | 870 | |
| Freight | 100 | |
| COD fee | 20 | |
| Withholding sales tax receivable | 10 | |
| **COD clearing account** | | **1,000** |

Withholding income tax and *other deductions* each get their own line the same way. If what reached the bank differs from the slip's
net, the difference is its own line on the **difference account** (debit when the bank is short, credit when over). It is never
folded into another line, and the Exception Queue already carries the matching finding.

## How the clearing account is meant to be used

The collection entry debits the courier's clearing account when the courier collects; the settlement entry credits the same
account with what the courier actually remits. The account's balance is therefore **what the couriers still hold**, and it should
trend to zero. A parcel collected but not yet remitted shows as a balance; an overdue one is also an exception in the queue.

## Setup (once per courier, app **Courier COD › Configuration › Couriers › Accounting** tab, needs Accounting access)

Journal (a miscellaneous one), clearing account, bank or receipts account, difference account, and one account for each deduction
type a slip reports. Only what a slip uses is required: a slip with no withholding does not need the withholding accounts, and a
slip that agrees with the bank does not need a difference account. A missing account is named in the error and nothing is written.

## Rules

- Only a Finance Controller can create the entry, and only on a remittance that is **posted and reconciled** with a bank amount.
  Finance does not need Accounting rights: the draft is created with elevated rights on purpose and records the Finance user as its creator.
  Opening the entry itself needs Accounting access.
- One entry per remittance. If the draft is deleted, or cancelled, a new one can be created. A posted entry stays.
- Not built: refunding a returned parcel's COD, and Pakistan chart-of-accounts
  specifics (account choice is configuration, so a local chart works without code changes).

## Reversing a posted entry (slice 1d, `pharma_courier_cod_accounting` 19.0.1.2.0)

A posted entry can be withdrawn, from the remittance (**Reverse entry**) or the shipment (**Reverse collection entry**).

1. A Finance Controller opens the wizard, gives a **reason** (required) and a date. Odoo's own reversal is created as a **draft**; the reason is on the
   reversal entry and in the record's history. Only a posted entry can be reversed; a draft is cancelled in Accounting instead, and an entry that
   already has a live reversal is refused.
2. An accountant posts the reversal. Nothing is posted by the module.
3. Once the reversal is **posted**, the record is released and a corrected entry can be created; the withdrawn entry is kept under *Superseded Entries*
   (accounting users). While the reversal is still a draft the original entry still stands, so nothing can be booked twice meanwhile.

The reversal is created without touching reconciliations. If the withdrawn entry had been reconciled against a customer invoice, that
reconciliation stays as it is until an accountant deals with it in Accounting.
