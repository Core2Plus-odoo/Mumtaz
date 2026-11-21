# Integration register

| ID | Integration | Direction | Owner (SoT) | Trigger | Auth | Idempotency key | Retry / failure | Monitoring | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INT-01 | Jawhar web ↔ Odoo `/jawhar/v1` | in | Odoo | user action | Odoo session cookie | n/a (synchronous, audited) | client retries idempotent GETs; POST errors shown | `jewellery.api.audit` | [VERIFIED] built, tested |
| INT-02 | Kiosk and client app public routes | in | Odoo | client | none / `X-Client-Token` | request cap per phone/day; 3 codes/hour | 400 with reason | audit | [VERIFIED] built, tested |
| INT-03 | ElevenLabs conversational agents | out (browser) | ElevenLabs | tap to talk | agent id (public), signed URL optional | n/a | falls back to server chat | none | [VERIFIED] built; live check needs a device |
| INT-04 | Anthropic Messages API | out | Odoo policy layer | agent run | `JAWHAR_ANTHROPIC_API_KEY` env | run id | local fallback phrase; refusal logged | `jewellery.ai.run` | [VERIFIED] optional |
| INT-05 | Gold rate JSON feed | in | feed provider (draft only) | hourly cron | HTTPS | last value + min change % | logged, skipped | `jewellery.rate.feed.log` | [VERIFIED] |
| INT-06 | Stripe billing | in (webhooks) / out | Stripe | webhook | signature | `mumtaz.stripe.event` id | **To verify** dedupe on event id | none | [VERIFIED exists] untested |
| INT-07 | ZATCA Phase 2 | out | ZATCA | invoice post/submit | certificates | invoice UUID | **To verify** retry | none | [VERIFIED exists] untested; decide vs native `l10n_sa_edi` |
| INT-08 | FBR Pakistan | out | FBR | submit | token | invoice UUID | To verify | none | [VERIFIED exists] untested |
| INT-09 | zaki-server ↔ Odoo XML-RPC | both | Odoo | signup/login/feature toggle | admin uid in service | n/a | generic errors | health endpoint | [VERIFIED by docs]; service account scope to review |
| INT-10 | C2P delivery API ↔ Odoo XML-RPC | both | Odoo | agent pipeline | encrypted connection record | engagement id | retry/backoff in `llm.py`; gated writes | run log | [VERIFIED by docs] |
| INT-11 | GitHub (generated modules push) | out | GitHub | deploy stage | token (encrypted) | branch + path | gated by policy | run log | [VERIFIED by docs] |
