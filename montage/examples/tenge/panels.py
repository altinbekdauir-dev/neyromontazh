import os
ROOT = os.environ.get("MONTAGE_ROOT", os.getcwd())
"""Self-made graphic panels (ref2 style: grid paper + tilted 3D card)."""
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FD = os.path.join(ROOT, "fonts/")
ACC = (236, 196, 146)
INK = (34, 30, 28)
RED = (196, 52, 40)
PW, PH = 1080, 920          # panel size (bottom part of the frame)


def F(kind, size):
    if kind == "bebas":
        return ImageFont.truetype(FD + "BebasNeueBold.otf", size)
    f = ImageFont.truetype(FD + "Montserrat[wght].ttf", size)
    vals = []
    for a in f.get_variation_axes():
        nm = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
        vals.append(600 if nm == "Weight" else a["default"])
    f.set_variation_by_axes(vals)
    return f


def eo(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3


def eio(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)


def grid_bg(w=PW, h=PH):
    im = Image.new("RGB", (w, h), (246, 245, 242))
    d = ImageDraw.Draw(im)
    for x in range(0, w, 60):
        d.line([(x, 0), (x, h)], fill=(214, 214, 214), width=2)
    for y in range(0, h, 60):
        d.line([(0, y), (w, y)], fill=(214, 214, 214), width=2)
    return im


GRID = grid_bg()


def card_on_grid(card, p, tilt=-4):
    """place RGBA card on the grid with shadow, pop-in by p (0..1)"""
    bg = GRID.copy().convert("RGBA")
    s = 0.85 + 0.15 * eo(p)
    c = card.resize((int(card.size[0] * s), int(card.size[1] * s)), Image.BICUBIC)
    c = c.rotate(tilt * (1 - 0.3 * eo(p)), resample=Image.BICUBIC, expand=True)
    a = c.split()[3]
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0)); blk = Image.new("RGBA", c.size, (20, 15, 10, 255))
    blk.putalpha(a.point(lambda v: int(v * 0.45))); sh = blk.filter(ImageFilter.GaussianBlur(22))
    x = (PW - c.size[0]) // 2; y = (PH - c.size[1]) // 2 + int((1 - eo(p)) * 120)
    bg.alpha_composite(sh, (x + 14, y + 26)); bg.alpha_composite(c, (x, y))
    return bg


def rounded(w, h, fill, r=34):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=fill)
    return im


def ctext(d, xy, txt, font, fill, anchor="mm"):
    d.text(xy, txt, font=font, fill=fill, anchor=anchor)


# ------------------------------------------------------------------ map (London -> Kazakhstan, 18 flights)
_world = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "world.json")))
LON0, LON1, LAT0, LAT1 = -12, 88, 33, 63
MW, MH = 940, 470
K = math.cos(math.radians(48))


def proj(lon, lat, w=MW, h=MH):
    x = (lon - LON0) / (LON1 - LON0) * w
    y = (LAT1 - lat) / (LAT1 - LAT0) * h
    return x, y


def _polys(feat):
    g = feat["geometry"]
    if g["type"] == "Polygon":
        return [g["coordinates"][0]]
    return [p[0] for p in g["coordinates"]]


_map_cache = {}


def base_map(S=2):
    if S in _map_cache:
        return _map_cache[S]
    im = Image.new("RGBA", (MW * S, MH * S), (233, 228, 218, 255))
    d = ImageDraw.Draw(im)
    for f in _world["features"]:
        nm = f["properties"]["name"]
        col = (205, 198, 186)
        if nm == "Kazakhstan":
            col = ACC
        elif nm == "United Kingdom":
            col = (190, 160, 120)
        for poly in _polys(f):
            pts = [tuple(v * S for v in proj(lo, la)) for lo, la in poly]
            if len(pts) > 2:
                d.polygon(pts, fill=col, outline=(246, 242, 234))
    _map_cache[S] = im
    return im


LONDON = (-0.13, 51.5)
ORAL = (51.37, 51.23)
ALMATY = (76.9, 43.25)


def arc_pts(a, b, n=80, bend=0.18):
    (x0, y0), (x1, y1) = proj(*a), proj(*b)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    cx, cy = mx + dy * bend, my - abs(dx) * bend
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
    return out


def plane_icon(size=46, ang=0):
    S = 4
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); c = size * S / 2; u = size * S / 46
    body = [(c - 20 * u, c), (c + 20 * u, c)]
    d.line(body, fill=INK, width=int(6 * u))
    d.polygon([(c + 2 * u, c), (c - 8 * u, c - 19 * u), (c - 3 * u, c - 19 * u), (c + 10 * u, c)], fill=INK)
    d.polygon([(c + 2 * u, c), (c - 8 * u, c + 19 * u), (c - 3 * u, c + 19 * u), (c + 10 * u, c)], fill=INK)
    d.polygon([(c - 18 * u, c), (c - 22 * u, c - 9 * u), (c - 19 * u, c - 9 * u), (c - 13 * u, c)], fill=INK)
    d.polygon([(c - 18 * u, c), (c - 22 * u, c + 9 * u), (c - 19 * u, c + 9 * u), (c - 13 * u, c)], fill=INK)
    d.ellipse([c + 16 * u, c - 3 * u, c + 23 * u, c + 3 * u], fill=INK)
    im = im.rotate(-ang, resample=Image.BICUBIC).resize((size, size), Image.LANCZOS)
    return im


def map_card(p, flights_t, total=18, title="ЛОНДОН — ҚАЗАҚСТАН"):
    """p: card pop-in progress; flights_t: seconds since flights started"""
    S = 2
    m = base_map(S).copy()
    d = ImageDraw.Draw(m)
    pts = [(x * S, y * S) for x, y in arc_pts(LONDON, ORAL)]
    # dashed route
    for i in range(0, len(pts) - 1, 2):
        d.line([pts[i], pts[i + 1]], fill=RED, width=5 * S // 2)
    for (lo, la), lab in ((LONDON, "ЛОНДОН"), (ORAL, "ҚАЗАҚСТАН")):
        x, y = proj(lo, la); x *= S; y *= S
        d.ellipse([x - 9 * S, y - 9 * S, x + 9 * S, y + 9 * S], fill=RED, outline=(255, 255, 255), width=3 * S)
        d.text((x, y - 22 * S), lab, font=F("bebas", 30 * S), fill=INK, anchor="mb")
    m = m.resize((MW, MH), Image.LANCZOS)
    # flights: each flight 0.16 s, counter
    per = 0.14
    n = 0
    if flights_t >= 0:
        n = min(total, int(flights_t / per) + 1)
        k = (flights_t / per) % 1 if n < total else 1.0
        path = arc_pts(LONDON, ORAL)
        idx = min(len(path) - 2, int(eio(k) * (len(path) - 1)))
        (x0, y0), (x1, y1) = path[idx], path[idx + 1]
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        pl = plane_icon(48, ang)
        m.alpha_composite(pl, (int(x0 - 24), int(y0 - 24)))
    card = rounded(MW + 60, MH + 200, (250, 248, 244, 255))
    card.alpha_composite(rounded(MW, MH, (0, 0, 0, 255), 22), (30, 30))  # mask frame
    mm = Image.new("RGBA", (MW, MH)); mask = rounded(MW, MH, (255, 255, 255, 255), 22).split()[3]
    card.paste(m, (30, 30), mask)
    d = ImageDraw.Draw(card)
    d.text((40, MH + 60), title, font=F("bebas", 64), fill=INK)
    num = f"{n}" if flights_t >= 0 else "0"
    d.text((MW + 20, MH + 52), num, font=F("bebas", 140), fill=RED, anchor="ra")
    d.text((MW + 20, MH + 178), "ӘСКЕРИ РЕЙС", font=F("msm", 30), fill=INK, anchor="rd")
    return card_on_grid(card, p, tilt=-3)


# ------------------------------------------------------------------ big number / date cards
def big_card(lines, p, tilt=3, w=860, h=560, bg=(250, 248, 244, 255)):
    """lines: list of (text, kind, size, color)"""
    card = rounded(w, h, bg)
    d = ImageDraw.Draw(card)
    tot = sum(int(s * (0.92 if k == "bebas" else 1.3)) for _, k, s, _ in lines)
    y = (h - tot) / 2
    for txt, k, s, col in lines:
        lh = int(s * (0.92 if k == "bebas" else 1.3))
        d.text((w / 2, y + lh / 2), txt, font=F(k, s), fill=col, anchor="mm")
        y += lh
    return card_on_grid(card, p, tilt)


def year_card(p, t):
    # 1993 with Soviet ruble crossed out
    card = rounded(860, 560, (250, 248, 244, 255)); d = ImageDraw.Draw(card)
    d.text((430, 250), "1993", font=F("bebas", 300), fill=INK, anchor="mm")
    d.text((430, 450), "РУБЛЬ АЙМАҒЫ", font=F("bebas", 80), fill=INK, anchor="mm")
    q = eio((t - 0.5) / 0.35)
    if q > 0:
        d.line([(190, 462), (190 + 480 * q, 440)], fill=RED, width=12)
    return card_on_grid(card, p, 3)


def months_card(p, t):
    card = rounded(860, 560, (250, 248, 244, 255)); d = ImageDraw.Draw(card)
    n = min(4, int(eo(t / 1.0) * 4) + 1) if t > 0 else 1
    d.text((300, 270), str(n), font=F("bebas", 360), fill=INK, anchor="mm")
    d.text((470, 220), "АЙ", font=F("bebas", 150), fill=INK, anchor="lm")
    d.text((470, 330), "НӨЛДЕН", font=F("msm", 52), fill=RED, anchor="lm")
    # progress bar
    q = eo(t / 1.0)
    d.rounded_rectangle([110, 470, 750, 500], 15, fill=(222, 216, 206))
    d.rounded_rectangle([110, 470, 110 + 640 * q, 500], 15, fill=ACC)
    return card_on_grid(card, p, -3)


def rate_card(p, t):
    card = rounded(900, 600, (250, 248, 244, 255)); d = ImageDraw.Draw(card)
    v = int(eo(t / 1.1) * 500) if t > 0 else 0
    d.text((450, 150), "1 ТЕҢГЕ", font=F("bebas", 190), fill=INK, anchor="mm")
    d.text((450, 290), "=", font=F("bebas", 110), fill=INK, anchor="mm")
    d.text((450, 430), f"{v} РУБЛЬ", font=F("bebas", 190), fill=RED, anchor="mm")
    d.text((450, 555), "АЛҒАШҚЫ БАҒАМ", font=F("msm", 38), fill=INK, anchor="mm")
    return card_on_grid(card, p, 3)


def date_card(p, t):
    # tear-off calendar page
    card = rounded(600, 640, (250, 248, 244, 255)); d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, 599, 150], 34, fill=RED); d.rectangle([0, 110, 599, 150], fill=RED)
    d.text((300, 80), "ҚАРАША · 1993", font=F("bebas", 80), fill=(255, 255, 255), anchor="mm")
    for x in (150, 450):
        d.ellipse([x - 16, -10, x + 16, 22], fill=(200, 196, 190))
    d.text((300, 400), "15", font=F("bebas", 380), fill=INK, anchor="mm")
    return card_on_grid(card, p, -4)


def sub_card(p, t):
    # subscribe button press
    card = Image.new("RGBA", (1000, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    pressed = 1.0 < t < 1.25
    col = RED
    y0 = 120 + (8 if pressed else 0)
    d.rounded_rectangle([100, y0, 900, y0 + 230], 115, fill=col)
    d.text((500, y0 + 118), "ЖАЗЫЛЫҢЫЗ", font=F("bebas", 150), fill=(255, 255, 255), anchor="mm")
    hx = 820 - 160 * eo(t / 0.9); hy = 470 - 150 * eo(t / 0.9)
    d.ellipse([hx - 26, hy - 26, hx + 26, hy + 26], fill=(255, 255, 255), outline=INK, width=6)
    return card_on_grid(card, p, 0)


# ------------------------------------------------------------------ media cards (photos / video frames)
MCW, MCH = 880, 560
_imgcache = {}


def load_img(path):
    if path not in _imgcache:
        _imgcache[path] = Image.open(path).convert("RGB")
    return _imgcache[path]


def fit_media(im, mode="cover", zoom=1.0, bg=(244, 241, 236)):
    w, h = im.size
    if mode == "cover":
        s = max(MCW / w, MCH / h) * zoom
    else:
        s = min((MCW - 40) / w, (MCH - 40) / h) * zoom
    r = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BICUBIC)
    out = Image.new("RGB", (MCW, MCH), bg)
    out.paste(r, ((MCW - r.size[0]) // 2, (MCH - r.size[1]) // 2))
    return out


def media_card(media_rgb, p, tilt=-3, label=None, cross=0.0, sub=None):
    b = 14
    card = rounded(MCW + 2 * b, MCH + 2 * b + ((140 if sub else 90) if label else 0), (252, 250, 246, 255), 30)
    mask = rounded(MCW, MCH, (255, 255, 255, 255), 20).split()[3]
    card.paste(media_rgb, (b, b), mask)
    d = ImageDraw.Draw(card)
    if cross > 0:
        q = eio(cross)
        d.line([(b + 60, b + 60), (b + 60 + (MCW - 120) * q, b + 60 + (MCH - 120) * q)], fill=RED, width=22)
        if cross > 0.5:
            q2 = eio((cross - 0.5) * 2)
            d.line([(b + MCW - 60, b + 60), (b + MCW - 60 - (MCW - 120) * q2, b + 60 + (MCH - 120) * q2)], fill=RED, width=22)
    if label:
        d.text((b + 10, MCH + 2 * b + 44), label, font=F("bebas", 70), fill=INK, anchor="lm")
        if sub:
            d.text((b + 12, MCH + 2 * b + 104), sub, font=F("msm", 32), fill=RED, anchor="lm")
    return card_on_grid(card, p, tilt)


_IL76 = None


def map_card_inset(p, flights_t, inset_path, inset_p):
    """map card with a small photo of the plane popping in at the top right"""
    bg = map_card(p, flights_t)
    if inset_p <= 0:
        return bg
    im = load_img(inset_path)
    w = 380; h = int(im.size[1] * w / im.size[0])
    ph = Image.new("RGBA", (w + 16, h + 16), (255, 255, 255, 255)); ph.paste(im.resize((w, h), Image.BICUBIC), (8, 8))
    s = 0.6 + 0.4 * eo(inset_p)
    ph = ph.resize((int(ph.size[0] * s), int(ph.size[1] * s)), Image.BICUBIC).rotate(6, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", ph.size, (20, 15, 10, 255)); sh.putalpha(ph.split()[3].point(lambda v: int(v * 0.4)))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    x, y = PW - ph.size[0] - 30, 40
    bg.alpha_composite(sh, (x + 8, y + 14)); bg.alpha_composite(ph, (x, y))
    return bg
