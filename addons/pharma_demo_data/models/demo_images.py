"""Placeholder product art for the DEMO shop. Pure Python + Pillow, no Odoo imports, so it can be
rendered and eyeballed on its own. Every image carries the word DEMO and "fictional": these are
stand-ins, not real products, and make no health claim of any kind."""
import base64
import io
import math

VERSION = "2"                   # bump to make existing DEMO databases re-render the pack art once
SIZE = 800                      # final px; drawn at 2x and downsampled for smooth edges
SS = 2

# sku -> (shape, letter, background tint, accent, label colour)
STYLES = {
    "DEMO-SKU-A": ("jar",    "A", (233, 241, 232), (110, 150, 118), (247, 250, 245)),   # sage
    "DEMO-SKU-B": ("bottle", "B", (247, 238, 222), (201, 156,  86), (253, 249, 240)),   # sand
    "DEMO-SKU-C": ("jar",    "C", (248, 234, 232), (196, 125, 120), (253, 246, 244)),   # rose
    "DEMO-SKU-D": ("bottle", "D", (235, 236, 246), (125, 120, 176), (247, 247, 252)),   # lavender
    "DEMO-SKU-E": ("jar",    "E", (249, 236, 224), (200, 120,  78), (253, 247, 241)),   # terracotta
}
DEFAULT_STYLE = ("jar", "?", (238, 240, 238), (120, 140, 125), (250, 250, 248))

_FONT_SERIF = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
_FONT_SANS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(ImageFont, paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:           # noqa: BLE001 - font not installed, try the next
            continue
    try:
        return ImageFont.load_default(size=size)        # Pillow >= 10.1
    except Exception:               # noqa: BLE001
        return ImageFont.load_default()


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _leaf(cx, cy, length, width, angle_deg, steps=40):
    """Lens-shaped leaf polygon centred on (cx, cy), rotated."""
    a = math.radians(angle_deg)
    top, bottom = [], []
    for i in range(steps + 1):
        t = i / steps
        x = (t - 0.5) * length
        y = math.sin(math.pi * t) * width / 2
        top.append((x, -y))
        bottom.append((x, y))
    pts = top + bottom[::-1]
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def _rrect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def render(code):
    """PNG bytes for a DEMO SKU code."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    shape, letter, bg, accent, label = STYLES.get(code, DEFAULT_STYLE)
    S = SIZE * SS
    img = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(img)

    # soft vertical wash, lighter at the top
    for y in range(0, S, 4):
        t = y / S
        d.rectangle([0, y, S, y + 4], fill=_mix((255, 255, 255), bg, 0.55 + 0.45 * t))
    # large soft circles
    over = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    od.ellipse([-S * .20, S * .50, S * .55, S * 1.15], fill=_mix(bg, accent, .18) + (255,))
    od.ellipse([S * .55, -S * .20, S * 1.15, S * .45], fill=_mix(bg, accent, .12) + (255,))
    img.paste(over.convert("RGB"), (0, 0), over.split()[3])
    d = ImageDraw.Draw(img)
    # botanical sprigs behind the pack: a stem with leaves fanned from its tip
    leaf_col = _mix(bg, accent, .34)
    for (bx, by, stem_deg, stem_len) in [(.10, .62, -62, .30), (.90, .64, -118, .30)]:
        a = math.radians(stem_deg)
        x0, y0 = S * bx, S * by
        x1, y1 = x0 + math.cos(a) * S * stem_len, y0 + math.sin(a) * S * stem_len
        d.line([x0, y0, x1, y1], fill=leaf_col, width=int(S * .008))
        for k, off in enumerate((-48, -18, 14, 44)):
            f = .42 + k * .16
            lx, ly = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            ang = stem_deg + off
            ar = math.radians(ang)
            ln, wd = S * .17, S * .055
            d.polygon(_leaf(lx + math.cos(ar) * ln / 2, ly + math.sin(ar) * ln / 2, ln, wd, ang), fill=leaf_col)
        ar = math.radians(stem_deg)
        d.polygon(_leaf(x1 + math.cos(ar) * S * .07, y1 + math.sin(ar) * S * .07, S * .15, S * .05, stem_deg), fill=leaf_col)

    # soft contact shadow
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([S * .26, S * .80, S * .74, S * .87], fill=(40, 50, 45, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(S * .012))
    img.paste(sh.convert("RGB"), (0, 0), sh.split()[3])
    d = ImageDraw.Draw(img)

    body = _mix(accent, (255, 255, 255), .05)
    dark = _mix(accent, (30, 40, 35), .35)
    if shape == "jar":
        bx0, bx1, by0, by1 = S * .27, S * .73, S * .36, S * .83
        _rrect(d, [bx0, by0, bx1, by1], S * .05, body)
        _rrect(d, [bx0 - S * .01, S * .26, bx1 + S * .01, S * .385], S * .03, dark)          # lid
        for k in range(6):                                                                    # lid ridges
            x = bx0 + S * .02 + k * (bx1 - bx0 - S * .04) / 5
            d.rectangle([x, S * .285, x + S * .006, S * .365], fill=_mix(dark, (255, 255, 255), .12))
        lab = [bx0 + S * .03, S * .47, bx1 - S * .03, S * .75]
    else:
        bx0, bx1, by0, by1 = S * .31, S * .69, S * .40, S * .84
        _rrect(d, [bx0, by0, bx1, by1], S * .06, body)                                        # body
        _rrect(d, [S * .41, S * .30, S * .59, S * .43], S * .03, body)                        # neck
        _rrect(d, [S * .395, S * .22, S * .605, S * .32], S * .025, dark)                     # cap
        lab = [bx0 + S * .03, S * .52, bx1 - S * .03, S * .77]
    # glass highlight
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([bx0 + S * .02, by0 + S * .03, bx0 + S * .055, by1 - S * .04],
                                         radius=S * .012, fill=(255, 255, 255, 70))
    img.paste(hl.convert("RGB"), (0, 0), hl.split()[3])
    d = ImageDraw.Draw(img)

    # label
    _rrect(d, lab, S * .025, label)
    lx0, ly0, lx1, ly1 = lab
    cxl = (lx0 + lx1) / 2
    d.polygon(_leaf(cxl, ly0 + (ly1 - ly0) * .22, S * .075, S * .028, -30), fill=accent)
    d.polygon(_leaf(cxl + S * .018, ly0 + (ly1 - ly0) * .22, S * .06, S * .024, 35), fill=_mix(accent, (255, 255, 255), .25))
    f_big = _font(ImageFont, _FONT_SERIF, int(S * .060))
    f_mid = _font(ImageFont, _FONT_SANS, int(S * .026))
    f_sml = _font(ImageFont, _FONT_SANS, int(S * .020))
    d.text((cxl, ly0 + (ly1 - ly0) * .52), "DEMO", fill=dark, font=f_big, anchor="mm")
    d.text((cxl, ly0 + (ly1 - ly0) * .74), f"PRODUCT {letter}", fill=accent, font=f_mid, anchor="mm")
    d.text((cxl, ly0 + (ly1 - ly0) * .90), "fictional", fill=_mix(accent, (90, 90, 90), .4), font=f_sml, anchor="mm")

    # footer strip so a screenshot of the card can never pass for a real product
    d.text((S * .5, S * .945), "DEMO IMAGE · FICTIONAL PRODUCT · NO HEALTH CLAIMS", fill=_mix(bg, (40, 50, 45), .55),
           font=_font(ImageFont, _FONT_SANS, int(S * .018)), anchor="mm")

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def b64(code):
    """base64 PNG for an Odoo binary field, or False if Pillow is unavailable. Never raises."""
    try:
        return base64.b64encode(render(code))
    except Exception:               # noqa: BLE001 - cosmetic only
        return False


def logo_png():
    """Transparent header logo: two-leaf mark + 'Pharma Demo Co' wordmark, canvas sized to the measured text."""
    from PIL import Image, ImageDraw, ImageFont
    H = 180 * SS
    f_name = _font(ImageFont, _FONT_SERIF, int(H * .27))
    f_tag = _font(ImageFont, _FONT_SANS, int(H * .098))
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    name_w = probe.textlength("Pharma Demo Co", font=f_name)
    tag_w = probe.textlength("EVERYDAY WELLNESS  ·  DEMO", font=f_tag)
    x_text = H * 1.10
    W = int(x_text + max(name_w, tag_w) + H * .12)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    forest, sage, clay = (47, 74, 58), (111, 148, 119), (181, 88, 58)
    cx, cy = H * .50, H * .52
    d.polygon(_leaf(cx - H * .06, cy, H * .56, H * .22, -52), fill=sage)
    d.polygon(_leaf(cx + H * .10, cy + H * .02, H * .48, H * .19, 28), fill=clay)
    d.line([cx - H * .20, cy + H * .26, cx + H * .06, cy - H * .02], fill=forest, width=int(H * .02))
    d.text((x_text, H * .46), "Pharma Demo Co", fill=forest, font=f_name, anchor="lm")
    d.text((x_text + H * .01, H * .76), "EVERYDAY WELLNESS  ·  DEMO", fill=sage, font=f_tag, anchor="lm")
    img = img.resize((W // SS, H // SS), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def logo_b64():
    try:
        return base64.b64encode(logo_png())
    except Exception:               # noqa: BLE001
        return False
