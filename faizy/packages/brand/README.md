# @faizy/brand

Single source of truth for the Faizy visual identity. All three apps consume the
Tailwind preset from here, so they cannot drift.

## The identity

| Token | Value |
|---|---|
| Primary orange | `#F69E22` |
| Black | `#0A0A0A` (near-black, deliberately not `#000`) |
| Neutrals | warm white / cream |
| Typeface | **Poppins** — Bold headlines, Medium labels, Regular body |
| Urdu | **Noto Nastaliq Urdu** |
| Tagline | حاضر ہیں۔ |
| Tone | bold, modern, sporty-confident. Short punchy headlines. |

**This replaces** the Royal Blue `#1A3FA5` / Gold `#C49A3C` / Cormorant Garamond
identity from the earlier prototypes. Nothing should ship with those values.

## The contrast rule

Brand orange on white is **~2.2:1** — it fails WCAG for text. Black on brand
orange is **~9:1** and passes comfortably.

So: **orange is a background colour, not a text colour.** The primary button is
orange-background/black-text, which is also the logo pairing. Before adding any
orange-text-on-light treatment, check it against the size you intend to use.

## Urdu rendering

Three things must all be true or Urdu renders wrong:

1. `lang="ur"` and `dir="rtl"` on the element.
2. Noto Nastaliq Urdu actually loaded — a generic serif fallback produces Naskh
   shaping, which reads as wrong to a native speaker.
3. The string kept intact. **Never** split it into characters or reverse it
   manually; the shaping engine does the joining. Manual handling is exactly what
   produces disconnected letterforms.

Nastaliq also needs far more line-height than Latin — `[lang="ur"]` is set to
`2.1` in each app's `globals.css`. That is functional, not decorative.

The `<UrduTagline />` component in `@faizy/ui` handles all of this.

## ⚠️ The logo is interim

`FaizyLogo` is a geometric reconstruction built to the written description of the
mark, **not a trace of the official artwork**. It must be replaced before launch.

To finish it:

1. Drop the source PNG from facebook.com/faizy.pk at `assets/logo-source.png`.
2. Trace it to clean vectors.
3. Replace the paths in `packages/ui/src/FaizyLogo.tsx` — the `FGlyph` component
   is the only thing that changes.

Sizing, colour variants (`circle` / `mono` / `inverse`), the lockup, and the
favicon/PWA icon pipeline are already wired, so it is a paths-only swap.

**PWA icons are also still missing** — `icon-192.png`, `icon-512.png` and
`maskable-512.png` are referenced by both manifests and need generating from the
final mark.

## Usage

```ts
// tailwind.config.ts
import { faizyPreset } from "@faizy/brand/tailwind";
export default { presets: [faizyPreset], content: [...] };
```

```tsx
import { FaizyLockup, UrduTagline, Button } from "@faizy/ui";
```

Prefer the semantic aliases (`surface`, `content`, `border`, `brand`) over raw
ramp values in app code — a token change then propagates without a
find-and-replace across three apps.
