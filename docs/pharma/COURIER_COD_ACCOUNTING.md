# Courier COD accounting (`pharma_courier_cod_accounting`, slice 1b)

One action on a **reconciled** courier remittance: **Create journal entry**. It makes a **draft** miscellaneous journal entry.
Nothing is posted for you: the accountant reviews and posts it in Accounting.

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

The customer's COD payment is registered the standard Odoo way against the courier's payment journal, so the courier's
clearing account is debited when the parcel is paid. The settlement entry then credits the same account with what the courier
actually remitted. The account's balance is therefore **what the courier still holds**, and it should trend to zero. This module does
not create the collection side; it closes it.

## Setup (once per courier, `Pharma › Configuration › Couriers › Accounting` tab, needs Accounting access)

Journal (a miscellaneous one), clearing account, bank or receipts account, difference account, and one account for each deduction
type a slip reports. Only what a slip uses is required: a slip with no withholding does not need the withholding accounts, and a
slip that agrees with the bank does not need a difference account. A missing account is named in the error and nothing is written.

## Rules

- Only a Finance Controller can create the entry, and only on a remittance that is **posted and reconciled** with a bank amount.
  Finance does not need Accounting rights: the draft is created with elevated rights on purpose and records the Finance user as its creator.
  Opening the entry itself needs Accounting access.
- One entry per remittance. If the draft is deleted, or cancelled, a new one can be created. A posted entry stays.
- Not in this slice: the collection entry itself, reversing a posted settlement, and Pakistan chart-of-accounts specifics
  (account choice is configuration, so a local chart works without code changes).
