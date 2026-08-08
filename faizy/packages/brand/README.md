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

## ⚠️ The logo is hand-built, not traced

`FaizyLogo` (and `assets/faizy-mark.svg`) follow the real mark's construction —
hollow angled wing for the top arm, solid mid bar flowing into a bowl counter,
tapering blade descender to a sharp point at lower-left — but the coordinates
were eyeballed from a reference image rather than traced. Expect a few percent of
drift on edge angles and terminal positions.

**Make it definitive before launch.** Five minutes:

1. Commit the source artwork at `assets/logo-source.png`.
2. Trace it, keeping corners sharp:

   ```bash
   convert logo-source.png -alpha remove -threshold 50% pbm:- \
     | potrace --svg --alphamax 0 --turdsize 8 -o traced.svg
   ```

   `--alphamax 0` disables curve smoothing. The default rounds off this mark's
   points, which is precisely what gives it its character.

3. Replace the two `<path>` elements in `FGlyph` (`packages/ui/src/FaizyLogo.tsx`)
   and in `assets/faizy-mark.svg`. Keep the two in sync — the standalone SVG is
   the source for icon generation.

Sizing, the three colour variants (`circle` / `mono` / `inverse`), the lockup and
the favicon pipeline all read from the component, so it is a paths-only swap.

**PWA icons are still missing** — `icon-192.png`, `icon-512.png` and
`maskable-512.png` are referenced by both manifests. Generate them from
`assets/faizy-mark.svg` once the paths are final:

```bash
for s in 192 512; do rsvg-convert -w $s -h $s assets/faizy-mark.svg -o icon-$s.png; done
```

For the maskable variant, scale the mark to ~80% inside the canvas so it survives
Android's circular crop.

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
