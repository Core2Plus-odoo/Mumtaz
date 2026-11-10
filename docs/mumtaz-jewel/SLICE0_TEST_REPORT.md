# Slice 0 test report (actual results)

Date: 2026-11-10. Branch: `claude/beautiful-keller-bmtykw`. Nothing was run on
any server; no production or real data was touched.

## What was run

One command: `scripts/jewel_ci.sh`. It refuses to run from `main`, refuses a
database name it did not generate, and never calls `deploy/update.sh`.

| Phase | What it did | Result |
| --- | --- | --- |
| 0 | Pure-Python engine tests (no database) | **19 passed, 0 failed** |
| 1 | Fresh database `jewel_ci_accept` created | OK |
| 2 | Install `mumtaz_jewellery,mumtaz_jewellery_vip,mumtaz_jewellery_owner` | OK, no ERROR or CRITICAL in the log |
| 3 | `TransactionCase` suite | **41 passed, 0 failed, 0 errors** |
| 4 | Seed `mumtaz_jewellery_demo` (synthetic DEMO data) | OK |

Odoo's own summary line, verbatim:

```
odoo.tests.result: 0 failed, 0 error(s) of 41 tests when loading database 'jewel_ci_guard'
```

Total: **60 tests, 0 failures, 0 errors.**

## Environment the numbers come from

| Item | Value |
| --- | --- |
| Odoo | 19.0 Community, shallow clone of branch `19.0`, run via `odoo-bin` |
| Python | 3.13.18 |
| PostgreSQL | 16.15 |
| Addons path | `<odoo>/addons,<repo>/addons` |
| Dependencies | Odoo's `requirements.txt`, with `psycopg2` replaced by `psycopg2-binary` and `python-ldap` omitted (neither builds without system headers; `auth_ldap` is not installed) |

Not yet verified anywhere: Postgres 15 (production compose pins
`postgres:15-alpine`), and any browser or tour test.

## The 41 TransactionCase tests

| Class | Tests | Covers |
| --- | --- | --- |
| `TestGoldRateApproval` | 15 | same-user refusal, non-manager refusal, approved-rate-only, two managers succeed, terminal states, the `allow_self_approval` escape hatch |
| `TestRateStateGuard` | 11 | the state guard described below: the ORM bypass is refused, for staff, managers and sudo alike, while draft rates stay editable and the buttons still work |
| `TestOldGoldExchange` | 5 | valuation from the approved rate, rate snapshot, threshold maker-checker, issued records cannot be cancelled, sequence |
| `TestPiece` | 7 | net weight, stone-weight and RFID constraints, breakdown equals the engine, dealer discount never touches metal, no price without an approved rate |
| `TestVipManagerCannotApproveRates` | 3 | the fifth user type: a VIP manager is not a jewellery manager |

Five user types are exercised: an employee with no jewellery group, a Jewellery
User, two distinct Jewellery Managers (maker and checker), and a VIP Manager.

### The four behaviours Slice 0 asked for

1. **Same-user approval is refused.** The manager who entered a rate gets
   `UserError` ("Maker-checker: a different user must approve a rate you
   entered") from `action_approve` *and* from `action_reject`; the rate stays
   `draft` with `approved_by_id` and `approved_at` empty. Confirmed.
2. **A non-manager is refused.** A Jewellery User gets `UserError` ("Only a
   jewellery manager can approve rates"); an employee with no jewellery group
   is refused as well; a VIP Manager is refused, because
   `group_vip_manager` implies `group_jewellery_user` only. Confirmed.
3. **An approved rate only.** `get_current` raises `UserError` when the only
   rate is `draft` or `rejected`; a later draft does not displace an approved
   rate; `stock.lot.get_price_breakdown` and `jewellery.old.gold.action_confirm`
   both refuse without one. The computed `jewellery_price` field shows `0.0`
   rather than inventing a number. Confirmed.
4. **Two managers succeed.** Manager A enters, manager B approves: state
   `approved`, `approved_by_id` is B, `approved_at` set, `create_uid` differs
   from `approved_by_id`, and `get_current` then returns that rate. Confirmed.

## Fixed during Slice 0: the maker-checker bypass

The gap flagged in the handoff was **verified real** by this suite and then,
on the owner's instruction, **fixed**:

- a Jewellery User could `write({'state': 'approved'})` on a draft rate, and
  `get_current` then returned it for pricing;
- a Jewellery User could `create` a rate that was already `approved`.

Neither path ran `action_approve`, so maker-checker was advisory: `state` is
read-only in the views only, and the ACL grants the user group write and
create.

The fix is a guard on `jewellery.gold.rate`:

- `create` refuses any `state` but `draft`, and refuses `approved_by_id` or
  `approved_at` set up front;
- `write` refuses `state`, `approved_by_id` and `approved_at` unless the write
  comes from `action_approve` or `action_reject`, which run the maker-checker
  checks first and set a context flag the guard looks for;
- the three fields are `copy=False`, so duplicating an approved rate gives a
  draft that needs its own approval;
- the guard holds for `sudo` as well. System code has no business approving a
  rate, so the Slice 1 rate feed enters a draft and a person decides on it.

The ACL was left alone deliberately: staff still need write on a draft rate to
correct a mistyped figure, which `test_the_other_fields_of_a_draft_are_still_editable`
covers. `TestRateStateGuard` has the 11 tests, including that managers and
`sudo` are refused too, and that the buttons still work through the guard.

### Still open: the same shape of hole on old gold

`jewellery.old.gold.state` is writable the same way — the ACL grants the user
group write, and `action_approve` is the only thing enforcing maker-checker, so
a user could in principle write `state` to `confirmed` and skip the second
person above the threshold. That was outside the change the owner approved, so
nothing was altered and no test asserts a refusal there yet. The remedy is the
same guard; it needs the same go-ahead.

## Deviations and things to know

- **Branch name.** This work is on `claude/beautiful-keller-bmtykw`, the branch
  this session was given, not `claude/mumtaz-jewellery-phase2` as
  `docs/mumtaz-jewel/CLAUDE.md` names. Both are feature branches and `main` was
  never touched, so the safety rule holds; rename or cherry-pick before merge
  if the documented name matters.
- **Two test bugs were mine, found by running the suite.** Odoo 19 overrides
  `assertRaises` and calls `issubclass()` on its argument, so it rejects a
  tuple of exception types. Both tests were rewritten and now pass.
- **Odoo's `--test-tags` skips plain `unittest.TestCase` classes.** The 19
  pre-existing engine tests did not run under the tag filter, so the CI script
  runs them as their own phase. Without that phase they are silently
  uncovered — worth knowing for anyone adding tests to `services/`.
- `--without-demo=all` is no longer valid in Odoo 19 (it warns and assumes
  `True`); the script passes `--without-demo=True`.
- Documents `ARCHITECTURE.md`, `FEATURE_GAP_ANALYSIS.md` and
  `BLUEPRINT_V2_RECONCILIATION.md` are referenced by the rules file but were
  not in the handoff, so no feature-gap row could be updated.

## The seed module

`addons/mumtaz_jewellery_demo` is synthetic only and every record is prefixed
`DEMO`. One install produced: 1 approved gold rate at 100.00/g, 3 products,
6 pieces (6 on hand), 4 clients across all four tiers, 1 piece out on approval,
1 old-gold intake valued 1246.08, and 4 owner decision cards.

The rate is seeded through the real maker-checker path — one demo manager
enters it, a different demo manager approves it — so the demo database
demonstrates the control instead of writing `approved` directly. The two demo
logins are created without a password and cannot sign in until someone sets
one. A marker parameter makes a second install a no-op.

Do not install this module on a database holding real client data.
