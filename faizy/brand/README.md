# Faizy brand

## The identity

| Token | Value |
|---|---|
| Primary orange | `#F69E22` |
| Black | `#0A0A0A` (near-black, deliberately not `#000`) |
| Neutrals | warm white / cream — `#FDFBF7`, `#FAF6EF` |
| Typeface | **Poppins** — Bold headlines, Medium labels, Regular body |
| Urdu | **Noto Nastaliq Urdu** |
| Tagline | حاضر ہیں۔ |
| Tone | bold, modern, sporty-confident. Short punchy headlines. |

**This replaces** the Royal Blue `#1A3FA5` / Gold `#C49A3C` / Cormorant Garamond
identity from the earliest prototypes. Nothing should ship with those values.

Implemented in `odoo/addons/faizy_website/static/src/scss/faizy.scss`, which is
the single place these values live for the website and portal.

## The contrast rule

Brand orange on white is **~2.2:1** — it fails WCAG for text. Black on brand
orange is **~9:1** and passes comfortably.

So: **orange is a background colour, not a text colour.** `.btn-faizy` is
orange-background / black-text, which is also the logo pairing. Before adding any
orange-text-on-light treatment, check it at the size you intend to use.

## Urdu rendering

Three things must all be true or Urdu renders wrong:

1. `lang="ur"` and `dir="rtl"` on the element.
2. Noto Nastaliq Urdu actually loaded — a generic serif fallback produces Naskh
   shaping, which reads as wrong to a native speaker. Loaded in
   `faizy_website_templates.xml` via the `faizy_fonts` layout inheritance.
3. The string kept intact. **Never** split it into characters or reverse it
   manually; the shaping engine does the joining. Manual handling is exactly what
   produces disconnected letterforms.

Nastaliq also needs far more line-height than Latin — `.faizy-urdu` sets `2.1`.
That is functional, not decorative.

Note the spelling: **حاضر** begins with ح (bari he), not ہ.

## ⚠️ The logo is hand-built, not traced

`faizy-mark.svg` follows the real mark's construction — hollow angled wing for
the top arm, solid mid bar flowing into a bowl counter, tapering blade descender
to a sharp point at lower-left — but the coordinates were eyeballed from a
reference image rather than traced. Expect a few percent of drift on edge angles
and terminal positions.

**Make it definitive before launch.** Five minutes:

1. Commit the source artwork at `logo-source.png`.
2. Trace it, keeping corners sharp:

   ```bash
   convert logo-source.png -alpha remove -threshold 50% pbm:- \
     | potrace --svg --alphamax 0 --turdsize 8 -o traced.svg
   ```

   `--alphamax 0` disables curve smoothing. The default rounds off this mark's
   points, which is precisely what gives it its character.

3. Update the paths in **both** places, then regenerate the icon:
   - `brand/faizy-mark.svg`
   - `POLYGONS` in `odoo/tools/make_icon.py`

   ```bash
   python3 odoo/tools/make_icon.py
   ```

CI fails if the committed icon no longer matches what the generator produces, so
the two cannot drift apart silently.

## Why the icon has its own generator

`odoo/tools/make_icon.py` rasterises the mark to
`faizy_core/static/description/icon.png` using only the standard library — a
scanline polygon fill and a hand-written PNG encoder. No ImageMagick, no rsvg, no
Pillow, because none of those is guaranteed on a deploy box, and a module whose
icon can only be rebuilt on one person's laptop is a module whose icon never gets
rebuilt.
