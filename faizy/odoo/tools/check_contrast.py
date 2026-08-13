#!/usr/bin/env python3
"""Assert the text/background pairs the design actually uses meet WCAG AA.

Written after the third one of these was found by eye on a live page rather
than before it shipped:

  - `.fz-card` inherited cream text onto a white card inside the dark hero.
  - The first warm palette used a clay that measured 3.73:1 behind 13px
    eyebrow labels. It looked fine.
  - `.fz-cta` set cream on itself, but `.fz-lead` sets its own colour and the
    warm layer had redefined that for the light page — so "No card needed to
    begin" rendered dark-on-dark at 3.32:1.

Every one of those was invisible to the compiler and to me. Contrast is not
something you can eyeball: 3.3:1 and 4.6:1 look about equally readable on a
good monitor, and only one of them is legible on a phone in sunlight.

This cannot infer which colour lands on which background — that needs a
rendered page. What it does is hold the pairs we KNOW the design uses to the
threshold, so changing a palette value fails here rather than on the site.

    python3 faizy/odoo/tools/check_contrast.py
"""

from __future__ import annotations

import sys

# ── Palette, mirrored from static/src/scss/faizy.scss ────────────────────
SAND = "#f7f1e7"
SAND_DEEP = "#efe5d6"
CARD = "#fffdfa"
INK = "#2b2622"
CLAY = "#8f4f08"
ORANGE = "#f69e22"
BLACK = "#0a0a0a"
CREAM = "#fdfbf7"
HEADER = "#fdf8f0"
WHITE = "#ffffff"

# WhatsApp's own #25D366 measures 1.88:1 on the header — a brand colour, not a
# text colour. These are the same hue two steps darker.
WHATSAPP = "#0b7a68"
WHATSAPP_DEEP = "#075e54"

# Alpha-composited text colours, since CSS uses rgba() over a known ground.
INK_72_ON_SAND = "#6b625b"
# Same value, promoted to $fz-ink-soft in the v6 portal layer, where it lands
# on cards as often as on sand — so it is held to both.
INK_SOFT = "#6b625b"
# The promo card's body copy, a touch lighter than ink on a warm tint.
PROMO_BODY = "#4a423b"
CREAM_78_ON_BLACK = "#c6c2bd"
CREAM_82_ON_WHATSAPP_DEEP = "#d1dfda"

# The printed invoice. A different rendering path from the site — a PDF, no
# webfonts — but the same rule decides the palette: Odoo paints primary_color
# onto the invoice heading, the total and the tagline as TEXT, and brand orange
# there measures 2.14:1. Clay is what the heading colour has to be.
PAPER = "#ffffff"

# The "this one is for me" band on the signup form: brand orange at 7% (13%
# once ticked) composited over the card. A tint, not a fill — orange as a
# background is the only place it is allowed.
TINT_7_ON_CARD = "#fef6eb"
TINT_13_ON_CARD = "#fef1de"

# (label, foreground, background, is_large_text)
# "Large" is WCAG's definition — 24px regular or 18.66px bold — not "looks big".
PAIRS = [
    ("body text on sand",            INK,               SAND,      False),
    ("body text on card",            INK,               CARD,      False),
    ("lead text on sand",            INK_72_ON_SAND,    SAND,      False),
    ("eyebrow label on sand",        CLAY,              SAND,      False),
    ("eyebrow label on sand-deep",   CLAY,              SAND_DEEP, False),
    ("accent heading on sand",       CLAY,              SAND,      True),
    ("button text on orange",        BLACK,             ORANGE,    False),
    ("heading on the dark CTA",      CREAM,             BLACK,     True),
    ("sub-copy on the dark CTA",     CREAM_78_ON_BLACK, BLACK,     False),
    ("tagline on the dark CTA",      ORANGE,            BLACK,     True),
    ("WhatsApp pill in the header",  WHATSAPP,          HEADER,    False),
    ("WhatsApp pill, hovered",       WHITE,             WHATSAPP_DEEP, False),
    ("contact banner label",         CREAM_82_ON_WHATSAPP_DEEP, WHATSAPP_DEEP, False),
    ("contact banner number",        WHITE,             WHATSAPP_DEEP, False),
    ("invoice heading on paper",     CLAY,              PAPER,     True),
    ("invoice field labels",         INK,               PAPER,     False),
    ("invoice total on paper",       CLAY,              PAPER,     False),
    ("total row, boxed layout",      WHITE,             CLAY,      False),
    ("self-check heading on tint",   CLAY,              TINT_7_ON_CARD,  False),
    ("self-check body on tint",      INK,               TINT_7_ON_CARD,  False),
    ("self-check heading, ticked",   CLAY,              TINT_13_ON_CARD, False),
    # The customer portal (v6 layer). Sand is the page ground and the content
    # sits on cream cards, so every pair here is one or the other.
    ("portal eyebrow on sand",       CLAY,              SAND,      False),
    ("portal title on sand",         INK,               SAND,      True),
    ("stat label on card",           INK_SOFT,          CARD,      False),
    ("stat value on card",           INK,               CARD,      False),
    ("section link on sand",         CLAY,              SAND,      False),
    ("table header label on card",   INK_SOFT,          CARD,      False),
    ("order reference on card",      CLAY,              CARD,      False),
    ("empty-state body on card",     INK_SOFT,          CARD,      False),
    ("portal WhatsApp button",       WHITE,             WHATSAPP,  False),
    ("family initial on orange",     BLACK,             ORANGE,    False),
    ("promo heading on tint",        INK,               TINT_7_ON_CARD,  True),
    ("promo body on tint",           PROMO_BODY,        TINT_7_ON_CARD,  False),
]


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    failures = []
    print(f"{'pair':30} {'ratio':>8}  {'needs':>6}")
    for label, fg, bg, large in PAIRS:
        ratio = contrast(fg, bg)
        threshold = 3.0 if large else 4.5
        ok = ratio >= threshold
        if not ok:
            failures.append((label, fg, bg, ratio, threshold))
        print(f"  {label:28} {ratio:6.2f}:1  {threshold:5.1f}  {'ok' if ok else 'FAIL'}")

    if failures:
        print(f"\n{len(failures)} pair(s) below WCAG AA:\n")
        for label, fg, bg, ratio, threshold in failures:
            print(
                f"  ✗ {label}: {fg} on {bg} is {ratio:.2f}:1, needs {threshold}:1"
            )
        return 1

    print(f"\nOK — all {len(PAIRS)} pairs meet WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
