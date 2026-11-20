# COD process flow (modules `pharma_courier_cod` and `pharma_courier_cod_accounting`)

One path for every parcel. Every parcel and every remittance shows **where it is, what comes next and who owns it**. These are computed from the real records, never typed.

```
 Booked -> In transit -> Delivered -> Collected -> Remitted -> Reconciled -> Closed        (Returned / Cancelled leave the path)
 Ops        Ops           Finance      Finance      Finance     Finance       -
                                       + collection entry: Finance creates, Accountant posts
                                                    + settlement entry: Finance creates, Accountant posts
```

| Stage | Next step | Owner |
| --- | --- | --- |
| Booked, In transit | Awaiting delivery | Operations |
| Delivered, nothing collected | Confirm what the courier collected | Finance Controller |
| Collected | Create the collection entry (needs `pharma_courier_cod_accounting`) | Finance Controller |
| | Post the collection entry | Accountant |
| | Awaiting the courier's remittance, or **Chase the overdue remittance** | Finance Controller |
| Remitted | Reconcile the remittance against the bank | Finance Controller |
| Reconciled | Create the settlement entry, then Post it | Finance Controller, then Accountant |
| Reconciled, entry withdrawn | Post the reversal, then create a corrected entry | Accountant, then Finance |
| Returned with COD still held | Settle the COD held on a returned parcel | Finance Controller |
| Closed | Nothing further | |

Exceptions (customer paid less, courier remitted less, overdue, deductions, no matching order) are a **parallel track**: they are worked in the Reconciliation app's Exception Queue with maker-checker. A parcel only shows how many findings it has open.

## Where people work (app **Courier COD**)

- **Pipeline**: every parcel by stage and courier, with the money outstanding.
- **Work Queue**: every parcel that needs someone, grouped by the step it waits for; filter by Operations, Finance Controller or Accountant.
- **Entries to Post** (accountants): every COD entry waiting to be posted. Collection, settlement and reversal entries are tagged when created, so the queue is exact.

Role setup: an accountant needs the Pharma user role (to see the app) and the Accounting invoicing role (to see Entries to Post and to post). Finance Controllers need no Accounting rights.

## Strict order, with a logged override

A slip cannot be settled until **every parcel on it has a posted collection entry**: settling cash the books never recorded as collected would leave the clearing account wrong. The error names the parcels.
Finance can override with a written reason on the slip (*Order Override Reason*); it is logged on the slip's history with the user. The owner can switch the process to advisory with the system parameter
`pharma.cod_flow_mode = advisory`, in which case the gap is only noted. Absent or any other value means strict. Nothing is posted by the modules in either mode.
