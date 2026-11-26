# Client Master Data & Access Request

> **CLIENT-FACING — C2P CONSULTANTS BRANDING. COVER EMAIL IS A DRAFT UNTIL
> APPROVED AND SENT BY AN AUTHORIZED C2P CONSULTANTS USER.**

| Document ID | C2P-MDR-`<PROJECT-REF>`-01 |
|---|---|
| Version | `<0.1>` |
| Status | `<Draft / In Review / Approved / Sent>` |
| Project reference | `<PROJECT-REF>` |
| Client | `<CLIENT LEGAL NAME>` |
| Project type | `<ERP / CUSTOM DEV / WEBSITE / AI & AUTOMATION / CONSULTING>` |
| Author | `<NAME>`, C2P Consultants |
| Approved by / date | `<NAME>` / `<YYYY-MM-DD>` |
| Return due | `<YYYY-MM-DD>` |

---

## Part A — cover email

**Subject:** Information we need to start `<PROJECT NAME>` — workbook attached

Dear `<FIRST NAME>`,

To build this correctly the first time we need some information from your side.
The attached workbook has one tab per topic. A few notes so it takes as little
of your time as possible:

- **We have only asked for what this project actually needs.** If a tab looks
  irrelevant to you, say so and we will confirm whether we can drop it.
- **Mandatory fields are marked.** Everything else is helpful but not blocking.
- **Every tab has an example row.** Please leave it in place and add yours below.
- **One named owner per tab** — tell us who that is and we will chase them, not
  you.
- **Partial is better than perfect.** Send what you have by `<YYYY-MM-DD>` and
  we will work with it rather than wait.

Please return it via `<SECURE RETURN METHOD — e.g. THE SECURE UPLOAD LINK BELOW,
NOT EMAIL, IF IT CONTAINS PERSONAL OR FINANCIAL DATA>`.

`<SECURE RETURN LINK OR INSTRUCTION>`

If any of this is held in a system we could read directly instead, tell us —
exporting is usually faster than retyping.

| | |
|---|---|
| Questions on content | `<PM NAME>` — `<EMAIL>` |
| Questions on anything commercial | `<ACCOUNT OWNER>` — `<EMAIL>` |

With best regards,

`<NAME>`, `<TITLE>`
C2P Consultants FZC LLC

---

## Part B — workbook structure

Machine-readable starting workbooks are in [`workbooks/`](workbooks/), one CSV
per tab. Build the client's `.xlsx` from the set matching the project type;
**delete the tabs this project does not need** before sending. Asking for data
you will not use costs you credibility on the first contact.

| Project type | Tabs to include |
|---|---|
| ERP implementation | Company & legal, Chart of accounts, Opening balances, Customers, Suppliers, Products & services, Tax config, Users & roles, System access |
| Custom development | Company & legal, Users & roles, System access, Integration endpoints, Test data |
| Website & ecommerce | Company & legal, Brand assets, Products & services, Content inventory, System access |
| AI & automation | Company & legal, Users & roles, System access, Integration endpoints, Process inventory |
| Consulting | Company & legal, Users & roles, Process inventory |

### Field instruction convention

Every tab carries these header rows so the client never has to guess:

| Row | Content |
|---|---|
| 1 | Tab purpose, one sentence |
| 2 | Named owner and return date |
| 3 | Column names |
| 4 | `MANDATORY` / `Optional` per column |
| 5 | Format and allowed values, e.g. `YYYY-MM-DD`, `ISO 4217 code` |
| 6 | A worked example row — leave in place |
| 7+ | Client data |

### Handling rules

- Classify the request before sending: does it ask for personal data, financial
  records or credentials? If yes, the secure return method is mandatory and
  email is not acceptable.
- **Never request a password.** Ask for an account to be created for a named C2P
  user, or for delegated access.
- Record what was received, when, from whom, and where it is stored.
- Chase through the missing-data reminder, which goes to the named tab owner —
  not a blanket reminder to the primary contact.
