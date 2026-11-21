# Jawhar design system v2 — "Vibrant Luxury Enterprise"

Source of truth for the public site: `website/jewel/site/jawhar.css`. The
product app (`apps/jawhar-web/src/styles.css`) is migrated to the same names
in Phase 2b; until then the app keeps its indigo tokens (recorded in
`DECISION_REGISTER.md` J-02).

## 1. Principles

1. Luxury is restraint with one vivid note: ivory ground, emerald action, gold only as a line or a highlight.
2. Numbers are the product: tabular numerals, the rate beside every price, nothing rounded on the client.
3. Truthful labels: the five readiness tags are the only status vocabulary on any surface.
4. Arabic is first-class: logical properties, RTL mirrored layouts, Arabic numerals in `ar`.
5. Motion is optional: one reveal on scroll, nothing that moves when the visitor asks it not to.

## 2. Colour tokens

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--emerald` / `-2` / `-deep` / `-soft` / `-line` | #0F6B55 / #168A6E / #0B4F3F / #E6F2EE / #BFD9CF | #2FB48F / #5CCBAD / #1E8C6E / #163528 / #2A5A47 | primary action, links, "built" |
| `--sapphire` / `-2` / `-soft` | #102C48 / #1A3F63 / #E8EEF5 | same / #16314D | ink, dark bands, enterprise |
| `--aubergine` / `-2` / `-soft` / `-line` | #482655 / #6A3D7D / #F1E8F4 / #D9C6E2 | #B98BCC (text) / #2A1A33 / #4A3058 | intelligence, "specified only" |
| `--gold` / `-2` / `-ink` / `-soft` / `-line` | #C4A464 / #D9BF86 / #7A5F22 / #F6EFDF / #E6D6AE | #D6BC7E / #E3CD98 / #E3CD98 / #2A2514 / #4C4323 | eyebrows, hairlines, "device pending" |
| `--teal` / `--teal-ink` / `--teal-soft` | #1ABC9C / #0E8C78 / #E3F6F1 | — / #5ED9BE / #0F2F2A | focus ring, "staging" |
| `--coral` / `--coral-soft` | #B42318 / #FDECEA | — / #2E1512 | errors |
| `--paper` / `--paper-2` / `--line` / `--surface` | #F7F3EC / #F0EAE0 / #E2D9CB / #FFFFFF | #0B1B2B / #122638 / #223A4F / #122638 | ground |
| `--ink` … `--ink-4` | #14202B / #2D3B4A / #5E6B7A / #8A96A3 | #F2EEE6 / #D5DCE4 / #9FB0C0 / #6F8192 | text |

Contrast: body ink on paper 13.5:1; emerald-deep on paper 7.6:1; gold-ink on
paper 5.6:1 (small text allowed); `--gold` itself is never used for text
under 24 px. Dark mode follows `prefers-color-scheme` and `data-theme`.

## 3. Typography

- Display: Cormorant Garamond 600 (h1 2.5–4.4 rem, h2 1.9–2.9 rem), italic for the one emphasised phrase.
- Body/UI: Plus Jakarta Sans 400–800, 17 px / 1.65.
- Arabic: IBM Plex Sans Arabic for `lang="ar"` or `dir="rtl"`; display falls back to the same (no Arabic serif pairing yet: open item).
- Numerals: `font-variant-numeric: tabular-nums` on every figure (`.num`).

## 4. Spacing, shape, depth

Scale 4·8·12·16·24·32·48·72·104 (`--s1`…`--s9`); radius 14 (cards) / 10 (controls) / pill; two shadows (`--shadow`, `--shadow-lg`); focus ring teal 3 px.

## 5. Components (site)

Header (sticky, blur, burger ≤1020 px), buttons (primary emerald, gold
gradient, ghost, dark, small), cards (icon, lift), screenshot figures,
readiness tags, chips, key/value rows, status table, notice, form fields,
checkbox consent, form messages, footer grid, reveal.

Readiness tags are fixed: `tag-built` Built & tested · `tag-staging`
Verified on staging · `tag-device` Device test pending · `tag-proto`
Specified only / In progress · `tag-plan` Planned.

## 6. Motion and accessibility

Reveal: 14 px rise, 0.6 s, once; disabled under `prefers-reduced-motion`.
Skip link, visible focus, labelled controls, `aria-expanded` on the menu,
`aria-live` on the form message, alt text on every content image (decorative
portraits empty alt), no colour-only meaning (tags carry text). Target:
WCAG 2.1 AA; automated axe pass PLANNED in CI.

## 7. Imagery policy

Product screenshots from the demo database (synthetic data) are the default.
AI-generated photography is allowed for brand imagery and is labelled on the
page. No stock photos of real people presented as clients. Agent portraits
are illustrations and say so.

## 8. App mapping (Phase 2b)

| App token (today) | Becomes |
| --- | --- |
| `--gold:#3D56C4` (indigo) | `--emerald` for actions; `--gold` reserved for highlights |
| `--teal` | `--teal-ink` for links, `--teal` for focus |
| kiosk theme | same tokens, dark sapphire ground with emerald accents |
| Plus Jakarta display | Cormorant for page titles only; UI stays sans |
