"""Рисует карточку Таро как картинку (Pillow). Ничего скачивать не нужно: рисунки создаются кодом."""

import colorsys
import io
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 700, 1200
GOLD = (214, 172, 82)
GOLD_TOP = (252, 236, 180)
GOLD_BOTTOM = (200, 152, 64)
TEXT_COLOR = (236, 228, 248)

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [
    os.path.join(BASE, "fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
    "/Library/Fonts",
]

ROMAN = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI",
         "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI"]

# Какой символ рисуем на какой карте (по порядку колоды в bot.py)
MOTIF_BY_INDEX = [
    "spiral", "infinity", "moon", "flower", "crown", "eye", "heart", "arrow",
    "infinity", "star", "wheel", "scales", "diamond", "butterfly", "hourglass",
    "flame", "lightning", "star", "moon", "sun", "burst", "globe",
]

_cache: dict = {}


def _font(names, size):
    for d in FONT_DIRS:
        for n in names:
            path = os.path.join(d, n)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _wrap(text, font, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.getlength(trial) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _background(idx):
    hue = (0.72 + idx * 0.043) % 1.0
    top = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.55, 0.18))
    bottom = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.05) % 1.0, 0.62, 0.40))
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    rng = random.Random(idx * 77 + 5)
    for _ in range(110):
        x, y = rng.randint(30, W - 30), rng.randint(30, H - 30)
        r = rng.choice([1, 1, 1, 2, 2, 3])
        a = rng.randint(100, 220)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(a, a, min(255, a + 30)))
    return img


def _gold_fill():
    grad = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = min(1.0, max(0.0, (y - 250) / 480))
        gd.line([(0, y), (W, y)], fill=tuple(int(GOLD_TOP[i] + (GOLD_BOTTOM[i] - GOLD_TOP[i]) * t) for i in range(3)))
    return grad


# ----------------------------- символы -----------------------------
def _poly(d, cx, cy, r, pts, fill=255):
    d.polygon([(cx + x * r, cy + y * r) for x, y in pts], fill=fill)


def _ellipse_poly(cx, cy, a, b, angle, n=48):
    pts = []
    ca, sa = math.cos(angle), math.sin(angle)
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = a * math.cos(t), b * math.sin(t)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def _star_pts(cx, cy, r_out, r_in, n):
    pts = []
    for i in range(n * 2):
        ang = -math.pi / 2 + i * math.pi / n
        rr = r_out if i % 2 == 0 else r_in
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def m_sun(d, cx, cy, r):
    for i in range(16):
        ang = i * math.pi / 8
        long = r if i % 2 == 0 else r * 0.8
        w = 0.11
        d.polygon([
            (cx + r * 0.58 * math.cos(ang - w), cy + r * 0.58 * math.sin(ang - w)),
            (cx + long * math.cos(ang), cy + long * math.sin(ang)),
            (cx + r * 0.58 * math.cos(ang + w), cy + r * 0.58 * math.sin(ang + w)),
        ], fill=255)
    d.ellipse([cx - r * .5, cy - r * .5, cx + r * .5, cy + r * .5], fill=255)
    d.ellipse([cx - r * .38, cy - r * .38, cx + r * .38, cy + r * .38], fill=0)
    d.ellipse([cx - r * .26, cy - r * .26, cx + r * .26, cy + r * .26], fill=255)


def m_moon(d, cx, cy, r):
    d.ellipse([cx - r * .8, cy - r * .8, cx + r * .8, cy + r * .8], fill=255)
    d.ellipse([cx - r * .3, cy - r * .92, cx + r * 1.1, cy + r * .5], fill=0)
    d.polygon(_star_pts(cx + r * .55, cy - r * .05, r * .26, r * .1, 4), fill=255)
    d.polygon(_star_pts(cx + r * .1, cy + r * .5, r * .15, r * .06, 4), fill=255)


def m_star(d, cx, cy, r):
    d.polygon(_star_pts(cx, cy, r, r * .42, 8), fill=255)
    d.ellipse([cx - r * .2, cy - r * .2, cx + r * .2, cy + r * .2], fill=0)
    d.ellipse([cx - r * .1, cy - r * .1, cx + r * .1, cy + r * .1], fill=255)


def m_heart(d, cx, cy, r):
    pts = []
    for i in range(120):
        t = 2 * math.pi * i / 120
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 15.5, cy + y * r / 15.5 + r * .05))
    d.polygon(pts, fill=255)
    inner = [(cx + (x - cx) * .72, cy + (y - cy) * .72) for x, y in pts]
    d.polygon(inner, fill=0)
    inner2 = [(cx + (x - cx) * .5, cy + (y - cy) * .5) for x, y in pts]
    d.polygon(inner2, fill=255)


def m_wheel(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    d.ellipse([cx - r * .88, cy - r * .88, cx + r * .88, cy + r * .88], fill=0)
    for i in range(8):
        ang = i * math.pi / 4
        d.line([(cx, cy), (cx + r * .9 * math.cos(ang), cy + r * .9 * math.sin(ang))], fill=255, width=12)
        d.ellipse([cx + r * math.cos(ang) - 14, cy + r * math.sin(ang) - 14,
                   cx + r * math.cos(ang) + 14, cy + r * math.sin(ang) + 14], fill=255)
    d.ellipse([cx - r * .28, cy - r * .28, cx + r * .28, cy + r * .28], fill=255)
    d.ellipse([cx - r * .14, cy - r * .14, cx + r * .14, cy + r * .14], fill=0)


def m_eye(d, cx, cy, r):
    top, bottom = [], []
    for i in range(41):
        t = -1 + i / 20
        y = (1 - t * t) * r * .55
        top.append((cx + t * r, cy - y))
        bottom.append((cx + t * r, cy + y))
    d.polygon(top + bottom[::-1], fill=255)
    d.ellipse([cx - r * .36, cy - r * .36, cx + r * .36, cy + r * .36], fill=0)
    d.ellipse([cx - r * .2, cy - r * .2, cx + r * .2, cy + r * .2], fill=255)
    for i in range(9):
        ang = math.pi + i * math.pi / 8
        d.line([(cx + r * 1.0 * math.cos(ang) * .0 + r * .9 * math.cos(ang) * .75, cy - r * .62 + r * .05 * math.sin(ang)),
                (cx + r * 1.15 * math.cos(ang) * .75, cy - r * .95)], fill=255, width=7)


def _teardrop(cx, cy, r, m=1.4, n=90):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = math.sin(t) * (math.sin(t / 2) ** m)
        y = -math.cos(t)
        pts.append((cx + x * r * .8, cy + y * r))
    return pts


def m_flame(d, cx, cy, r):
    d.polygon(_teardrop(cx, cy + r * .05, r), fill=255)
    d.polygon(_teardrop(cx, cy + r * .28, r * .66), fill=0)
    d.polygon(_teardrop(cx, cy + r * .45, r * .4), fill=255)


def m_lightning(d, cx, cy, r):
    _poly(d, cx, cy, r, [(.15, -1), (-.55, .12), (-.08, .12), (-.3, 1), (.55, -.2), (.08, -.2), (.5, -1)])


def m_scales(d, cx, cy, r):
    d.line([(cx, cy - r * .85), (cx, cy + r * .85)], fill=255, width=14)
    d.line([(cx - r * .85, cy - r * .5), (cx + r * .85, cy - r * .5)], fill=255, width=14)
    d.ellipse([cx - 22, cy - r * .85 - 22, cx + 22, cy - r * .85 + 22], fill=255)
    d.polygon([(cx - r * .45, cy + r * .9), (cx + r * .45, cy + r * .9), (cx, cy + r * .7)], fill=255)
    for sx in (-1, 1):
        x = cx + sx * r * .85
        d.line([(x, cy - r * .5), (x - r * .32, cy + r * .15)], fill=255, width=7)
        d.line([(x, cy - r * .5), (x + r * .32, cy + r * .15)], fill=255, width=7)
        d.pieslice([x - r * .38, cy - r * .1, x + r * .38, cy + r * .5], 0, 180, fill=255)


def m_hourglass(d, cx, cy, r):
    d.rectangle([cx - r * .62, cy - r * .95, cx + r * .62, cy - r * .8], fill=255)
    d.rectangle([cx - r * .62, cy + r * .8, cx + r * .62, cy + r * .95], fill=255)
    _poly(d, cx, cy, r, [(-.5, -.8), (.5, -.8), (.06, 0), (.5, .8), (-.5, .8), (-.06, 0)])
    _poly(d, cx, cy, r, [(-.36, -.7), (.36, -.7), (0, -.08)], fill=0)
    _poly(d, cx, cy, r, [(-.36, .72), (.36, .72), (0, .3)], fill=0)
    _poly(d, cx, cy, r, [(-.22, .72), (.22, .72), (0, .4)], fill=255)
    d.line([(cx, cy - r * .1), (cx, cy + r * .35)], fill=255, width=5)


def m_crown(d, cx, cy, r):
    _poly(d, cx, cy, r, [(-.8, .35), (-.8, -.45), (-.4, -.05), (0, -.75), (.4, -.05), (.8, -.45), (.8, .35)])
    d.rectangle([cx - r * .8, cy + r * .42, cx + r * .8, cy + r * .72], fill=255)
    for x, y in [(-.8, -.45), (0, -.75), (.8, -.45)]:
        d.ellipse([cx + x * r - 16, cy + y * r - 16, cx + x * r + 16, cy + y * r + 16], fill=255)
    for x in (-.45, 0, .45):
        d.ellipse([cx + x * r - 10, cy + .1 * r - 10, cx + x * r + 10, cy + .1 * r + 10], fill=0)


def m_butterfly(d, cx, cy, r):
    for sx in (-1, 1):
        d.polygon(_ellipse_poly(cx + sx * r * .5, cy - r * .35, r * .55, r * .38, sx * -0.6), fill=255)
        d.polygon(_ellipse_poly(cx + sx * r * .38, cy + r * .45, r * .38, r * .27, sx * 0.5), fill=255)
        d.ellipse([cx + sx * r * .55 - r * .14, cy - r * .42 - r * .14, cx + sx * r * .55 + r * .14, cy - r * .42 + r * .14], fill=0)
        d.line([(cx, cy - r * .5), (cx + sx * r * .35, cy - r * .95)], fill=255, width=5)
    d.rounded_rectangle([cx - 11, cy - r * .55, cx + 11, cy + r * .75], radius=11, fill=255)


def m_infinity(d, cx, cy, r):
    pts = []
    for i in range(241):
        t = 2 * math.pi * i / 240
        den = 1 + math.sin(t) ** 2
        pts.append((cx + r * 1.0 * math.cos(t) / den, cy + r * 1.05 * math.sin(t) * math.cos(t) / den))
    d.line(pts, fill=255, width=26, joint="curve")
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=255)
    d.polygon(_star_pts(cx, cy - r * .62, r * .18, r * .07, 4), fill=255)


def m_flower(d, cx, cy, r):
    for i in range(8):
        ang = i * math.pi / 4
        d.polygon(_ellipse_poly(cx + r * .52 * math.cos(ang), cy + r * .52 * math.sin(ang), r * .5, r * .2, ang), fill=255)
    d.ellipse([cx - r * .3, cy - r * .3, cx + r * .3, cy + r * .3], fill=0)
    d.ellipse([cx - r * .2, cy - r * .2, cx + r * .2, cy + r * .2], fill=255)


def m_diamond(d, cx, cy, r):
    _poly(d, cx, cy, r, [(0, -1), (.62, -.15), (0, 1), (-.62, -.15)])
    for pts in ([(-.62, -.15), (.62, -.15)], [(0, -1), (.22, -.15), (0, 1)], [(0, -1), (-.22, -.15), (0, 1)]):
        d.line([(cx + x * r, cy + y * r) for x, y in pts], fill=0, width=6)


def m_arrow(d, cx, cy, r):
    _poly(d, cx, cy, r, [(0, -1), (.5, -.3), (-.5, -.3)])
    d.rectangle([cx - r * .13, cy - r * .35, cx + r * .13, cy + r * .85], fill=255)
    _poly(d, cx, cy, r, [(-.13, .6), (-.4, .95), (-.13, .95)])
    _poly(d, cx, cy, r, [(.13, .6), (.4, .95), (.13, .95)])
    d.ellipse([cx - r * .85, cy - r * .85, cx + r * .85, cy + r * .85], outline=255, width=8)


def m_spiral(d, cx, cy, r):
    pts = []
    for i in range(400):
        t = i / 399
        ang = t * 3.2 * 2 * math.pi
        rr = r * (0.08 + 0.92 * t)
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.line(pts, fill=255, width=18, joint="curve")
    ex, ey = pts[-1]
    d.ellipse([ex - 17, ey - 17, ex + 17, ey + 17], fill=255)


def m_globe(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=12)
    d.ellipse([cx - r * .5, cy - r, cx + r * .5, cy + r], outline=255, width=8)
    d.line([(cx, cy - r), (cx, cy + r)], fill=255, width=8)
    d.line([(cx - r, cy), (cx + r, cy)], fill=255, width=8)
    d.arc([cx - r * .9, cy - r * .55, cx + r * .9, cy + r * .55], 0, 180, fill=255, width=7)
    d.arc([cx - r * .9, cy - r * .55, cx + r * .9, cy + r * .55], 180, 360, fill=255, width=7)


def m_burst(d, cx, cy, r):
    for i in range(24):
        ang = i * math.pi / 12
        long = r if i % 2 == 0 else r * .72
        d.line([(cx + r * .3 * math.cos(ang), cy + r * .3 * math.sin(ang)),
                (cx + long * math.cos(ang), cy + long * math.sin(ang))], fill=255, width=9 if i % 2 == 0 else 6)
    d.ellipse([cx - r * .3, cy - r * .3, cx + r * .3, cy + r * .3], fill=255)
    d.ellipse([cx - r * .2, cy - r * .2, cx + r * .2, cy + r * .2], fill=0)
    d.ellipse([cx - r * .1, cy - r * .1, cx + r * .1, cy + r * .1], fill=255)


MOTIFS = {
    "sun": m_sun, "moon": m_moon, "star": m_star, "heart": m_heart, "wheel": m_wheel,
    "eye": m_eye, "flame": m_flame, "lightning": m_lightning, "scales": m_scales,
    "hourglass": m_hourglass, "crown": m_crown, "butterfly": m_butterfly,
    "infinity": m_infinity, "flower": m_flower, "diamond": m_diamond, "arrow": m_arrow,
    "spiral": m_spiral, "globe": m_globe, "burst": m_burst,
}


# ----------------------------- сама карта -----------------------------
def _render(idx, name, text, watermark):
    img = _background(idx)
    d = ImageDraw.Draw(img, "RGBA")

    # рамки
    d.rectangle([16, 16, W - 16, H - 16], outline=GOLD, width=5)
    d.rectangle([32, 32, W - 32, H - 32], outline=GOLD, width=2)
    for x, y in [(16, 16), (W - 16, 16), (16, H - 16), (W - 16, H - 16)]:
        d.polygon([(x, y - 14), (x + 14, y), (x, y + 14), (x - 14, y)], fill=GOLD)

    # номер
    f_num = _font(["DejaVuSerif-Bold.ttf"], 52)
    d.text((W // 2, 98), ROMAN[idx], font=f_num, fill=GOLD_TOP, anchor="mm")
    d.line([(W // 2 - 120, 150), (W // 2 - 14, 150)], fill=GOLD, width=2)
    d.line([(W // 2 + 14, 150), (W // 2 + 120, 150)], fill=GOLD, width=2)
    d.polygon([(W // 2, 142), (W // 2 + 8, 150), (W // 2, 158), (W // 2 - 8, 150)], fill=GOLD)

    # рамка для рисунка
    ax0, ay0, ax1, ay1 = 70, 180, W - 70, 790
    d.rounded_rectangle([ax0, ay0, ax1, ay1], radius=22, fill=(8, 4, 24, 120), outline=GOLD, width=3)
    cx, cy = W // 2, (ay0 + ay1) // 2
    for rad, wd in [(250, 2), (236, 1)]:
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(214, 172, 82, 140), width=wd)
    for i in range(24):
        ang = i * math.pi / 12
        px, py = cx + 243 * math.cos(ang), cy + 243 * math.sin(ang)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(246, 224, 160, 200))

    # символ со свечением
    mask = Image.new("L", (W, H), 0)
    MOTIFS[MOTIF_BY_INDEX[idx]](ImageDraw.Draw(mask), cx, cy, 175)
    glow = mask.filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.75))
    img.paste(Image.new("RGB", (W, H), GOLD), mask=glow)
    img.paste(_gold_fill(), mask=mask)
    d = ImageDraw.Draw(img, "RGBA")

    # название
    size = 62
    while size > 28:
        f_name = _font(["DejaVuSerif-Bold.ttf"], size)
        if f_name.getlength(name.upper()) <= W - 150:
            break
        size -= 2
    d.text((W // 2, 850), name.upper(), font=f_name, fill=GOLD_TOP, anchor="mm")
    d.line([(150, 900), (W // 2 - 14, 900)], fill=GOLD, width=2)
    d.line([(W // 2 + 14, 900), (W - 150, 900)], fill=GOLD, width=2)
    d.polygon([(W // 2, 892), (W // 2 + 8, 900), (W // 2, 908), (W // 2 - 8, 900)], fill=GOLD)

    # предсказание
    f_text = _font(["DejaVuSerif-Italic.ttf", "DejaVuSerif.ttf"], 26)
    lines = _wrap(text, f_text, W - 150)
    y = 945
    for line in lines[:6]:
        d.text((W // 2, y), line, font=f_text, fill=TEXT_COLOR, anchor="mm")
        y += 36

    if watermark:
        f_wm = _font(["DejaVuSerif-Italic.ttf", "DejaVuSerif.ttf"], 22)
        d.text((W // 2, H - 52), watermark, font=f_wm, fill=(214, 172, 82, 230), anchor="mm")
    return img


def render_card(idx: int, name: str, text: str, watermark: str = "") -> bytes:
    """Возвращает JPEG-байты карточки. Результат кэшируется."""
    key = (idx, watermark)
    if key not in _cache:
        buf = io.BytesIO()
        _render(idx, name, text, watermark).save(buf, format="JPEG", quality=92)
        _cache[key] = buf.getvalue()
    return _cache[key]
