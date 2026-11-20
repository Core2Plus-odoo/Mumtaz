# Looking after Premium and Royal clients

How the tiers differ in practice, and what the software has to do about each
difference. A proposal: the tiers and the restrictions exist in code today,
the service rules below are mostly not built and some are policy rather than
software.

The principle is narrow and worth stating: **a private client is not a
standard client with a badge.** The things that make them valuable — the
relationship manager knows them, the business is discreet, the purchases are
large and irregular — are exactly the things a generic CRM gets wrong by
treating them as a segment to campaign at.

## The four tiers

| Tier | Who | What changes |
| --- | --- | --- |
| **Standard** | Walk-in, first purchases | Normal service; may use the client app and automated messages, with consent |
| **Preferred** | Repeat buyer, known at a branch | A named associate, occasions tracked, invited to previews |
| **Private** | Significant, relationship-led | Named relationship manager **and** a deputy; record restricted; no automated outbound; discreet billing available |
| **Royal / Protocol** | Protocol, ruling-family or equivalent | Everything above, plus: the owner or a named senior is the contact, no agent above read-and-recommend, viewings come to them, nothing about them leaves the building |

## 1. Who may see the record — built

A global record rule restricts Private and Royal clients to the named
relationship manager, the deputy and VIP managers. Everyone else does not see
the record at all — not a redacted version, not a name in a list.

**Gap:** opening a record writes to the access log; a list view, an export or
an RPC read does not. See `FUNCTIONAL_REVIEW.md` finding 1. For this tier
that gap matters more than for any other, and it is the first thing I would
close if the answer to "who looked at this client?" ever has to be defended.

## 2. Who may contact them — built, and deliberately restrictive

- **No automated outbound, ever.** Not a campaign, not an occasion reminder,
  not a rate alert. The system drafts; a person sends.
- **An agent is capped.** Private and Royal clients are capped at draft level
  — their data never enters a model request, and no agent sends on their
  behalf.
- **Royal goes further:** the contact is the owner or a named senior, not the
  branch. A reminder lands on *their* list, not the associate's.

What that looks like in the product: the stylist runs the same reasoning for
a Private client and produces the same suggestions, then hands the draft to
the relationship manager with the wording ready in both languages. The client
gets a message from a person who knows her.

## 3. Discretion in the paperwork — partly built

- **Discreet billing**: the invoice goes to a billing contact who may not be
  the client, which matters for gifts and for family arrangements. The flag
  exists; the invoicing behaviour behind it is Slice 1.
- **No marketing**: a hard flag, honoured above any campaign.
- **Naming**: the demo deliberately shows `A. K.` rather than a full name.
  Worth deciding whether restricted records display initials to anyone
  outside the named pair.

## 4. How they are served — mostly policy, some software

| Practice | What the software does |
| --- | --- |
| Viewings at home, in a suite, or out of hours | Pieces on approval with a return date, an insured value and a reminder; the appointment is a calendar activity on the named manager |
| The tray comes to them | Three to five pieces chosen for that client, with reasons; shared as an expiring revocable link, or carried |
| Nothing is ever "out of stock" at the wrong moment | The slow-stock and transfer views exist so the piece can be moved between stores before the viewing, not after |
| A second pair of eyes on money | Old gold over the threshold needs a different person; the till warns before a cash reporting limit is crossed |
| Continuity when the manager is away | The deputy field is first-class, not a note — they see the record, the occasions and the pieces out |

## 5. What should follow, and does not yet

1. **Log every read of a restricted record**, not only an opened one.
2. **An escalation path on the record**: who covers when both the manager and
   the deputy are unavailable, and after how long.
3. **A quiet period** per client — "do not contact between these dates" —
   which outranks occasions and campaigns.
4. **Household and gifting links**: a spouse, a family office, an assistant
   who buys on their behalf. Today they are separate records with no
   relationship, which is how a surprise gets spoiled.
5. **Proof of provenance on demand**: certificate, weight, karat and the rate
   the piece was priced at, as a single document.
6. **A protocol note on the record** — how they are addressed, who may call,
   what time of day. Unglamorous, and the thing staff actually get wrong.

## 6. What I would not build

- **Scoring Private and Royal clients.** The odds model is useful for a
  pipeline of ordinary opportunities. Ranking a protocol client by predicted
  probability is both useless and, if it were ever seen, offensive.
- **Any automated outbound to them**, even with consent captured. The cost of
  one wrong automated message to this tier is the relationship.
- **Putting their data in a model request** to improve a suggestion. The
  suggestion is not worth it.
