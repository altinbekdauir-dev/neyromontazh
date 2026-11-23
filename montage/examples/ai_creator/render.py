"""v2: all-caps captions with reference-style animations.
anims (per word): blur | drop (letters fall in) | flip (letters flip in, gold) | neon (warm flicker)
card types: stack | roll (rolling line) | stair (depth staircase)
exits: blur | dust (particle dissolve) | squash (3D fold) | streak (horizontal smear) | scatter
"""
import sys, json, subprocess, os, glob, math
ROOT = os.environ.get("MONTAGE_ROOT", os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageChops

W, H, FPS = 1080, 1920, 30
SRC = os.environ.get("SRC", os.path.join(ROOT, "input", "source.mov"))
WORDS = json.load(open(os.path.join(ROOT, "words.json")))
CUT = 5.167
WHITE_END = 1.70
PREVIEW = os.environ.get("PREVIEW")
DUR = 32.25
FD = os.path.join(ROOT, "fonts/")
WARM = (255, 246, 236)
rng = np.random.default_rng(3)

# ------------------------------------------------------------------ fonts
_fc = {}


def font(kind, size):
    k = (kind, size)
    if k in _fc:
        return _fc[k]
    spec = {
        "black": ("Inter[opsz,wght].ttf", {"Weight": 900, "Optical size": 32}),
        "xbold": ("Inter[opsz,wght].ttf", {"Weight": 800, "Optical size": 24}),
        "cond": ("Oswald[wght].ttf", {"Weight": 700}),
        "serif": ("PlayfairDisplay-Italic[wght].ttf", {"Weight": 600}),
        "mono": ("IBMPlexMono-Regular.ttf", None),
        "bebas": ("BebasNeueBold.otf", None),
        "msm": ("Montserrat[wght].ttf", {"Weight": 600}),
        "script": ("GoodVibesPro.ttf", None),
    }[kind]
    f = ImageFont.truetype(FD + spec[0], size)
    if spec[1]:
        vals = []
        for a in f.get_variation_axes():
            nm = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
            vals.append(spec[1].get(nm, a["default"]))
        f.set_variation_by_axes(vals)
    _fc[k] = f
    return f


def ease_out(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)


def back_out(x):
    x = min(max(x, 0), 1); c = 1.9; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


GOLD_STOPS = [(0, (255, 244, 200)), (0.42, (236, 186, 82)), (0.52, (176, 116, 34)), (0.75, (226, 170, 66)), (1, (255, 226, 140))]


def gradient(h, stops):
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, 3))
    for c in range(3):
        out[:, c] = np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops])
    return out


def glyph(txt, kind, size, color=WARM, gold=False, glow=None, extrude=0, tracking=0, pad=70, shadow=True):
    """Render text to RGBA. Returns (img, pad, ascent, mask L)."""
    f = font(kind, size)
    if glow:
        pad = max(pad, int(size * 0.6))
    if tracking:
        ws = [f.getlength(c) + tracking for c in txt]
        w = int(sum(ws) - tracking)
    else:
        w = int(f.getlength(txt))
    asc, desc = f.getmetrics()
    Wd, Hd = w + 2 * pad, asc + desc + 2 * pad
    m = Image.new("L", (Wd, Hd), 0)
    d = ImageDraw.Draw(m)
    if tracking:
        x = pad
        for c, cw in zip(txt, ws):
            d.text((x, pad), c, font=f, fill=255); x += cw
    else:
        d.text((pad, pad), txt, font=f, fill=255)
    out = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    if shadow:
        sh = m.filter(ImageFilter.GaussianBlur(max(3, size * 0.10))).point(lambda v: int(v * 0.6))
        L = Image.new("RGBA", (Wd, Hd), (18, 9, 4, 0)); L.putalpha(sh)
        out.alpha_composite(L, (0, int(size * 0.05)) if size * 0.05 < pad else (0, 0))
    if extrude:
        for k in range(extrude, 0, -1):
            L = Image.new("RGBA", (Wd, Hd), (52 + 2 * k, 38 + 2 * k, 30 + k, 255)); L.putalpha(m)
            o = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0)); o.paste(L, (k // 2, k)); out.alpha_composite(o)
    if glow:
        for r, gain in ((size * 0.09, 0.55), (size * 0.035, 0.9)):
            g = m.filter(ImageFilter.GaussianBlur(r)).point(lambda v, gg=gain: min(255, int(v * gg)))
            L = Image.new("RGBA", (Wd, Hd), glow + (0,)); L.putalpha(g); out.alpha_composite(L)
    if gold:
        gr = gradient(Hd - 2 * pad, GOLD_STOPS)
        fillarr = np.zeros((Hd, Wd, 4), np.uint8)
        fillarr[pad:Hd - pad, :, :3] = gr[:, None, :]
        fillarr[:pad, :, :3] = gr[0]; fillarr[Hd - pad:, :, :3] = gr[-1]
        fillarr[..., 3] = np.asarray(m)
        out.alpha_composite(Image.fromarray(fillarr))
    else:
        L = Image.new("RGBA", (Wd, Hd), tuple(color) + (255,)); L.putalpha(m); out.alpha_composite(L)
    return out, pad, asc, m


# ------------------------------------------------------------------ styles (ALL CAPS)
STY_OLD = {
    "kick":  dict(kind="xbold", size=62, tracking=4),
    "kickS": dict(kind="xbold", size=46, tracking=6, color=(255, 236, 214)),
    "roll":  dict(kind="black", size=108),
    "rollS": dict(kind="serif", size=118),
    "big":   dict(kind="black", size=165),
    "mid":   dict(kind="black", size=120),
    "huge":  dict(kind="black", size=215, extrude=8),
    "cond":  dict(kind="cond", size=200, extrude=8),
    "serif": dict(kind="serif", size=130),
    "serifL": dict(kind="serif", size=150),
    "neon":  dict(kind="black", size=130, color=(255, 248, 238), glow=(255, 168, 86)),
    "gold":  dict(kind="black", size=180, gold=True, glow=(255, 150, 40)),
    "goldC": dict(kind="cond", size=150, gold=True, glow=(255, 150, 40)),
    "condL": dict(kind="cond", size=130),
    "plus":  dict(kind="black", size=170, gold=True, glow=(255, 150, 40)),
}


ACC = (236, 196, 146)
STY = {
    "S":  dict(kind="msm", size=64, lower=True),                  # small top/bottom words (like 'все уже слышали')
    "kb": dict(kind="bebas", size=96, tracking=2),                # small caps (hook labels)
    "B":  dict(kind="bebas", size=250, tracking=1),               # big headline, white (new word flashes beige)
    "A":  dict(kind="bebas", size=250, tracking=1, color=ACC, acc=True),   # big headline, stays beige
    "N":  dict(kind="bebas", size=250, tracking=2, color=(255, 248, 238), glow=(255, 168, 86)),
    "G":  dict(kind="script", size=150, fb="S"),
}
from fontTools.ttLib import TTFont as _TT
_GV = set(_TT(FD + "GoodVibesPro.ttf").getBestCmap().keys())


def script_text(t):
    t = t.lower().replace("і", "i").replace("һ", "h")
    return t if all(ord(ch) in _GV for ch in t) else None


class Cur:
    i = 0


def wd(style, n=1, text=None, anim="blur"):
    ws = WORDS[Cur.i:Cur.i + n]; Cur.i += n
    t = text if text is not None else " ".join(w["w"] for w in ws)
    if t not in ("«+»",) and not t.endswith("?"):
        t = t.rstrip(",.")
    if t == "«+»":
        t = "+"
    if STY[style]["kind"] == "script":
        st = script_text(t)
        if st is None:
            style = STY[style]["fb"]
        else:
            t = st
    if STY[style]["kind"] != "script":
        t = t.lower() if STY[style].get("lower") else t.upper()
    return dict(text=t, style=style, t=ws[0]["s"], te=ws[-1]["e"], anim=anim)


CARDS = []


def card(lines, kind="stack", x=540, y=300, behind=False, exit="blur", end=None, maxw=980, gap=0, delay_to=None, stair=None):
    if delay_to:
        k = 0
        for ln in lines:
            for w in ln:
                w["t"] = max(w["t"], delay_to + k * 0.07); k += 1
    CARDS.append(dict(lines=lines, kind=kind, x=x, y=y, behind=behind, exit=exit, end=end, maxw=maxw, gap=gap, stair=stair))


# ===================================================================== EDIT
def S(n=1, t=None): return wd("S", n, t)
def B(n=1, t=None, anim="blur"): return wd("B", n, t, anim)
def A(n=1, t=None): return wd("A", n, t)
def N(n=1, t=None): return wd("N", n, t, "neon")
def G(n=1, t=None): return wd("G", n, t)
def KB(n=1, t=None): return wd("kb", n, t)


# HOOK (labels like the approved screenshot, accent colour instead of gold)
card([[KB(1, "ақша")], [B(1, "таппайтын")], [KB(2, "ИИ КРЕАТОР")]], x=790, y=230, end=3.62, maxw=440)
card([[KB(1, "ақша")], [A(1, "табатын")], [KB(2, "ИИ КРЕАТОР")]], x=290, y=230, end=3.62, maxw=440)
card([[B(1)], [A(1)]], end=CUT + 0.05, exit="dust")                                   # АЙЫРМАШЫЛЫҒЫ / ҚАНДАЙ?
# SEATED — layout: small words on top, big headline, small words below
card([[S(), S(), S()], [B(), B()], [S(), S()]], exit="squash")                         # әртүрлі промтты алып / ТРЕНДТЕГІ ВИДЕО / жасап жүрсіз
card([[S()], [B(2, "ақша жоқ")]], exit="dust")                                          # бірақ / АҚША ЖОҚ
card([[S(), S()], [N()], [G(2, "ете алмайсыз")]], delay_to=10.25, exit="streak")      # әрі қарай / МОНЕТИЗИРОВАТЬ / ете алмайсыз
card([[S(), S(), S()], [B()]])                                                          # әрі қарай не / ІСТЕЙМІЗ?
card([[S()], [B(), B()]])                                                               # мысалы / МЕНІМЕН БІРГЕ
card([[S(), S(), S()], [N()]], exit="squash")                                          # жұмыс істеп жүрген / ОҚУШЫЛАРЫМ
card([[S()], [B(1, anim="drop")], [S()]], exit="scatter")                               # с / НУЛЯ / келіп
card([[S()], [B()], [S()]], exit="streak")                                              # өзінің / ҚАБІЛЕТТЕРІН / шыңдап
card([[B()], [G()]], exit="dust")                                                       # МИЛЛИОННИК / блогерлардан
card([[S(), S()], [B(), B()]])                                                          # осындай чектарға / ЗАКАЗ АЛЫП
card([[S(), S()], [B()], [S()]])                                                        # және де / СОТРУДНИЧЕСТВА / арқылы
card([[S()], [A()], [S(), S()]], exit="dust")                                           # осындай / ТАБЫСҚА / шығып жатыр
card([[S(), S(), S()], [B(), B()]])                                                     # егер тренд қана / ЖАСАП ҚОЙМАЙ
card([[B()], [S(), S()]], exit="dust")                                                  # ТАБЫСҚА / шыққыңыз келсе
card([[S()], [A(), B()]], end=DUR + 1)                                                  # комментарийге / + ҚАЛДЫРЫҢЫЗ
assert Cur.i == len(WORDS), (Cur.i, len(WORDS))

for c in CARDS:
    c["t0"] = min(w["t"] for ln in c["lines"] for w in ln)
for k, c in enumerate(CARDS):
    if c["end"] is None:
        nxt = CARDS[k + 1]["t0"] if k + 1 < len(CARDS) else DUR
        last = max(w["te"] for ln in c["lines"] for w in ln)
        c["end"] = min(nxt, last + 1.5)
json.dump([dict(exit=c['exit'], xs=c['xs'] if 'xs' in c else 0) for c in CARDS], open('/dev/null', 'w'))
for c in CARDS:
    fl = sorted([w for ln in c["lines"] for w in ln], key=lambda w: w["t"])
    for k, w in enumerate(fl):
        w["tn"] = fl[k + 1]["t"] if k + 1 < len(fl) else w["t"] + 0.6
json.dump([dict(text=w["text"], style=w["style"], t=w["t"]) for c in CARDS for ln in c["lines"] for w in ln], open(os.path.join(ROOT, "appear.json"), "w"), ensure_ascii=False)
EXIT_DUR = {"blur": 0.16, "dust": 0.75, "squash": 0.2, "streak": 0.18, "scatter": 0.3}
# exits that take longer start a bit earlier so next card is clean
for c in CARDS:
    c["xs"] = c["end"] - EXIT_DUR[c["exit"]] * (0.55 if c["exit"] == "dust" else 1.0)
json.dump([dict(exit=c["exit"], xs=c["xs"]) for c in CARDS if c["end"] < DUR], open(os.path.join(ROOT, "exits.json"), "w"))

# ------------------------------------------------------------------ prerender / layout


def make_word(w, scale=1.0):
    st = dict(STY[w["style"]]); kind = st.pop("kind"); size = int(st.pop("size") * scale); st.pop("fb", None); st.pop("lower", None); acc = st.pop("acc", False)
    if "extrude" in st:
        st["extrude"] = max(3, int(st["extrude"] * scale))
    w["size"] = size; w["kind"] = kind
    im, pad, asc, m = glyph(w["text"], kind, size, **st)
    w["im"], w["pad"], w["asc"], w["w"] = im, pad, asc, im.size[0] - 2 * pad
    w["im_acc"] = None
    if not acc and kind != "script" and not st.get("glow"):
        st2 = dict(st); st2["color"] = ACC
        w["im_acc"] = glyph(w["text"], kind, size, **st2)[0]
    bb = m.getbbox() or (0, pad, 1, pad + asc)
    w["ia"] = pad + asc - bb[1]
    w["ib"] = max(0, bb[3] - (pad + asc)) * (0.55 if kind == "script" else 1.0)
    if w["anim"] in ("drop", "flip"):
        f = font(kind, size); tr = st.get("tracking", 0)
        chars = []
        for i, ch in enumerate(w["text"]):
            if ch == " ":
                continue
            dx = f.getlength(w["text"][:i]) + tr * i
            cim, cpad, _, _ = glyph(ch, kind, size, **st)
            chars.append(dict(im=cim, dx=int(dx) - cpad + pad, i=i))
        w["chars"] = chars


for c in CARDS:
    if c["kind"] == "roll":
        sp = []
        for w in c["lines"][0]:
            parts = w["text"].split()
            if len(parts) == 1:
                sp.append(w); continue
            tot = sum(len(p) for p in parts); acc = 0
            for p in parts:
                d = dict(w); d["text"] = p
                d["t"] = w["t"] + (w["te"] - w["t"]) * acc / tot; acc += len(p)
                sp.append(d)
        c["lines"][0] = sp
        ws = c["lines"][0]
        for w in ws:
            make_word(w)
            if w["w"] > 900:
                make_word(w, 900 / w["w"])
        x = 0
        for w in ws:
            w["lx"] = x; x += w["w"] + 30
        c["lineasc"] = max(w["asc"] for w in ws)
        c["y"] = 385 - c["lineasc"]
        continue
    c["behind"] = False  # text stays above the head with a gap, never on the head
    BOTTOM = 455 if c["t0"] < CUT else 385
    TOP = 135
    for scale in (1.0, 0.92, 0.84, 0.76, 0.68, 0.6):
        prev_bottom = None
        for li, ln in enumerate(c["lines"]):
            for w in ln:
                make_word(w, scale)
            sp = 70 if (len(ln) > 1 and all(w["style"] == "S" for w in ln)) else 24
            total = sum(w["w"] for w in ln) + sp * (len(ln) - 1)
            if total > c["maxw"]:
                sp = 24
                total = sum(w["w"] for w in ln) + sp * (len(ln) - 1)
            if total > c["maxw"]:
                f = c["maxw"] / total
                for w in ln:
                    make_word(w, scale * f)
                total = sum(w["w"] for w in ln) + sp * (len(ln) - 1)
            above = max(w["ia"] for w in ln); below = max(w["ib"] for w in ln)
            base = above if prev_bottom is None else prev_bottom + 12 + above
            x = c["x"] - total / 2 + (c["stair"][li][0] if c["stair"] else 0)
            for w in ln:
                w["x"] = int(x - w["pad"]); w["y"] = int(base - w["asc"] - w["pad"])
                x += w["w"] + sp
            prev_bottom = base + below
        last = c["lines"][-1]
        base = max(w["y"] + w["pad"] + w["asc"] for w in last)
        dy = BOTTOM - base
        top = min(w["y"] + w["pad"] + w["asc"] - w["ia"] for ln in c["lines"] for w in ln) + dy
        if top >= TOP:
            break
    for ln in c["lines"]:
        for w in ln:
            w["y"] += dy

# ------------------------------------------------------------------ drawing helpers


def comp(canvas, im, x, y):
    x, y = int(x), int(y)
    cx0, cy0 = max(0, x), max(0, y)
    cx1, cy1 = min(W, x + im.size[0]), min(H, y + im.size[1])
    if cx1 <= cx0 or cy1 <= cy0:
        return
    canvas.alpha_composite(im.crop((cx0 - x, cy0 - y, cx1 - x, cy1 - y)), (cx0, cy0))


def alpha_mul(im, a):
    if a >= 0.999:
        return im
    im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * a))); return im


def xform(im, a=1.0, blur=0.0, sx=1.0, sy=1.0):
    if sx != 1 or sy != 1:
        nw, nh = max(1, int(im.size[0] * sx)), max(1, int(im.size[1] * sy))
        im = im.resize((nw, nh), Image.BILINEAR)
    if blur > 0.5:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return alpha_mul(im, a)


def place(canvas, im0, x, y, a=1.0, blur=0.0, sx=1.0, sy=1.0, dy=0):
    im = xform(im0, a, blur, sx, sy)
    comp(canvas, im, x + (im0.size[0] - im.size[0]) / 2, y + (im0.size[1] - im.size[1]) / 2 + dy)


def neon_alpha(p_frames):
    seq = [0.0, 0.9, 0.15, 1.0, 0.35, 1.0, 0.7, 1.0]
    return seq[p_frames] if p_frames < len(seq) else 1.0


def shine(im, phase):
    """diagonal light sweep over gold text; phase 0..1"""
    if phase <= 0 or phase >= 1:
        return im
    w, h = im.size
    band = np.zeros((h, w), np.float32)
    xs = np.arange(w)[None, :] + np.arange(h)[:, None] * 0.5
    c = -h * 0.5 + phase * (w + h)
    band = np.clip(1 - np.abs(xs - c) / 60.0, 0, 1)
    arr = np.asarray(im).astype(np.float32)
    a = arr[..., 3:4] / 255.0
    arr[..., :3] = np.minimum(255, arr[..., :3] + band[..., None] * 160 * a)
    return Image.fromarray(arr.astype(np.uint8))


def draw_word(canvas, w, t, ex_q, ex_kind, extra=None):
    """in-animation by w['anim'], exit progress ex_q (0..1)"""
    tin = w["t"] - 0.04
    if t < tin:
        return
    p = (t - tin)
    x, y = w["x"], w["y"]
    if extra:
        x += extra.get("dx", 0); y += extra.get("dy", 0)
    a_ex, b_ex, sy_ex, sx_ex, dy_ex = 1, 0, 1, 1, 0
    if ex_q > 0:
        if ex_kind == "squash":
            sy_ex = max(0.02, 1 - ease_io(ex_q)); sx_ex = 1 + 0.12 * ex_q; b_ex = 8 * ex_q; a_ex = 1 - ex_q ** 2
        elif ex_kind == "streak":
            sx_ex = 1 + 1.6 * ease_io(ex_q); sy_ex = max(0.1, 1 - 0.75 * ex_q); b_ex = 10 * ex_q; a_ex = 1 - ex_q
        elif ex_kind == "blur":
            a_ex = 1 - ease_io(ex_q); b_ex = 18 * ex_q; dy_ex = -14 * ex_q
    ex_a_mult = extra.get("a", 1) if extra else 1
    ex_blur = extra.get("blur", 0) if extra else 0
    ex_sc = extra.get("sc", 1) if extra else 1
    anim = w["anim"]
    if anim in ("drop", "flip") and not (ex_q > 0 and ex_kind == "scatter"):
        im_total = None
        for k, ch in enumerate(w["chars"]):
            st = 0.035 * k
            q = (p - st) / (0.32 if anim == "drop" else 0.26)
            if q <= 0:
                continue
            cim = ch["im"]
            if anim == "drop":
                off = (1 - back_out(q)) * (-90 if k % 2 == 0 else 70)
                a = ease_out(q * 1.4); bl = (1 - ease_out(q)) * 10
                place(canvas, cim, x + ch["dx"], y + off + dy_ex, a * a_ex * ex_a_mult, bl + b_ex, sx_ex, sy_ex)
            else:  # flip
                sx = abs(math.cos((1 - ease_out(q)) * math.pi / 2)) if q < 1 else 1
                a = ease_out(q * 2)
                place(canvas, cim, x + ch["dx"], y + dy_ex, a * a_ex * ex_a_mult, b_ex, max(0.03, sx) * sx_ex, sy_ex)
        if anim == "flip" and p > 0.035 * len(w["chars"]) + 0.3:
            # shine sweep on settled gold word (over the per-letter render): redraw whole word with shine
            ph = ((p - 0.035 * len(w["chars"]) - 0.3) % 2.2) / 0.7
            if ph < 1:
                place(canvas, shine(w["im"], ph), x, y + dy_ex, a_ex * ex_a_mult, b_ex, sx_ex, sy_ex)
        return
    if ex_q > 0 and ex_kind == "scatter" and anim in ("drop", "flip"):
        for k, ch in enumerate(w["chars"]):
            r = np.random.default_rng(k + 11)
            vx, vy = r.uniform(-140, 140), r.uniform(-320, -120)
            place(canvas, ch["im"], x + ch["dx"] + vx * ex_q, y + vy * ex_q, 1 - ex_q, 12 * ex_q)
        return
    q = p / 0.26
    a = ease_out(q); bl = (1 - ease_out(q)) * 14; sc = 1 + (1 - ease_out(q)) * 0.04
    if anim == "neon":
        a *= neon_alpha(int(p * FPS))
        bl = 0; sc = 1
    if ex_q > 0 and ex_kind == "scatter":
        a_ex = 1 - ex_q; b_ex = 14 * ex_q; dy_ex = -60 * ex_q
    if w.get("im_acc") is not None:
        k = min(1.0, max(0.0, (t - w["tn"]) / 0.25))
        if k < 1:
            place(canvas, w["im_acc"], x, y, a * a_ex * ex_a_mult * (1 - k), bl + b_ex + ex_blur, sc * sx_ex * ex_sc, sc * sy_ex * ex_sc, dy_ex)
        if k > 0:
            place(canvas, w["im"], x, y, a * a_ex * ex_a_mult * k, bl + b_ex + ex_blur, sc * sx_ex * ex_sc, sc * sy_ex * ex_sc, dy_ex)
        return
    place(canvas, w["im"], x, y, a * a_ex * ex_a_mult, bl + b_ex + ex_blur, sc * sx_ex * ex_sc, sc * sy_ex * ex_sc, dy_ex)


def draw_roll(canvas, c, t, ex_q):
    ws = c["lines"][0]
    vis = [w for w in ws if w["t"] - 0.04 <= t]
    if not vis:
        return

    def target(n):
        L = ws[0]["lx"]; R = ws[n - 1]["lx"] + ws[n - 1]["w"]
        if R - L <= 980:
            return (L + R) / 2 - 540
        nl = ws[n - 1]["lx"]
        return min(R - 990, nl - 90) if ws[n - 1]["w"] <= 900 else (nl + R) / 2 - 540

    # smooth shift between targets
    n = len(vis)
    sh_prev = target(max(1, n - 1)); sh_new = target(n)
    q = ease_out((t - vis[-1]["t"] + 0.04) / 0.28)
    shift = sh_prev + (sh_new - sh_prev) * q if n > 1 else sh_new
    for w in vis:
        xc = w["lx"] + w["w"] / 2 - shift
        d = (xc - 540) / 540.0
        p = (t - w["t"] + 0.04)
        qi = ease_out(p / 0.26)
        sc = (1 - 0.22 * d * d) * (1 + (1 - qi) * 0.12)
        a = qi * max(0.0, min(1.0, 1.6 - abs(d) * 1.1))
        bl = (1 - qi) * 16 + max(0, abs(d) - 0.5) * 14
        yy = c["y"] + c["lineasc"] - w["asc"] - w["pad"] + 70 * d * d
        x0 = w["lx"] - shift - w["pad"]
        if ex_q > 0:
            a *= 1 - ease_io(ex_q); bl += 16 * ex_q
        place(canvas, w["im"], x0, yy, a, bl, sc, sc, -(1 - qi) * 20)


def draw_stair(canvas, c, t, ex_q):
    ws = [w for ln in c["lines"] for w in ln]
    vis = [w for w in ws if w["t"] - 0.04 <= t]
    n = len(vis)
    for k, w in enumerate(vis):
        age = n - 1 - k   # 0 = newest
        if age == 0:
            extra = {}
        else:
            extra = dict(a=0.88 ** age, blur=1.6 * age, sc=0.94 ** age, dy=18 * age)
        draw_word(canvas, w, t, ex_q, "blur", extra)


# ------------------------------------------------------------------ dust (particle dissolve)
_dust = {}


def card_snapshot(c):
    t = c["xs"] - 0.001
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for ln in c["lines"]:
        for w in ln:
            draw_word(cv, w, t, 0, "blur")
    return np.asarray(cv).astype(np.float32)


def dust_frame(c, t, canvas_arr):
    """canvas_arr float HxWx4 to accumulate into"""
    key = id(c)
    if key not in _dust:
        snap = card_snapshot(c)
        ys, xs = np.nonzero(snap[..., 3] > 90)
        sel = rng.random(len(ys)) < 0.35
        ys, xs = ys[sel], xs[sel]
        x0, x1 = (xs.min(), xs.max()) if len(xs) else (0, 1)
        r = np.random.default_rng(5)
        noise = Image.fromarray((r.random((H // 16, W // 16)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        noise = np.asarray(noise, np.float32) / 255.0
        act = c["xs"] + (np.arange(W)[None, :] - x0) / max(1, (x1 - x0)) * 0.38 + noise * 0.14
        _dust[key] = dict(snap=snap, ys=ys, xs=xs, act=act, pact=act[ys, xs],
                          vx=r.uniform(60, 260, len(ys)), vy=r.uniform(-200, -30, len(ys)),
                          col=snap[ys, xs, :3], a0=snap[ys, xs, 3])
    D = _dust[key]
    keep = (D["act"] > t).astype(np.float32)[..., None]
    canvas_arr += 0  # noop
    solid = D["snap"].copy(); solid[..., 3:4] *= keep
    # composite solid
    a = solid[..., 3:4] / 255.0
    canvas_arr[..., :3] = canvas_arr[..., :3] * (1 - a) + solid[..., :3] * a
    canvas_arr[..., 3:4] = np.maximum(canvas_arr[..., 3:4], solid[..., 3:4])
    dt = t - D["pact"]
    m = (dt > 0) & (dt < 0.7)
    if m.any():
        d = dt[m]
        px = (D["xs"][m] + D["vx"][m] * d + 40 * d * d).astype(int)
        py = (D["ys"][m] + D["vy"][m] * d - 60 * d * d).astype(int)
        al = D["a0"][m] * (1 - d / 0.7) ** 1.5
        ok = (px >= 0) & (px < W - 1) & (py >= 0) & (py < H - 1)
        px, py, al, col = px[ok], py[ok], al[ok], D["col"][m][ok]
        buf = np.zeros((H, W), np.float32); cb = np.zeros((H, W, 3), np.float32)
        for ox, oy in ((0, 0), (1, 0), (0, 1)):
            np.add.at(buf, (py + oy, px + ox), al)
            np.add.at(cb, (py + oy, px + ox), col * al[:, None])
        cb = cb / np.maximum(buf, 1e-3)[..., None]
        buf = np.minimum(buf, 255)
        pa = buf[..., None] / 255.0
        canvas_arr[..., :3] = canvas_arr[..., :3] * (1 - pa) + cb * pa
        canvas_arr[..., 3:4] = np.maximum(canvas_arr[..., 3:4], buf[..., None])


# ------------------------------------------------------------------ checks
CHECK_DIR = os.path.join(ROOT, "checks")
CHECKS = [Image.open(f).convert("RGB") for f in sorted(glob.glob(CHECK_DIR + "/*.png"))]
names = [w["w"] for w in WORDS]
CHK_T0 = WORDS[names.index("осындай")]["s"]
CHK_T1 = WORDS[names.index("арқылы")]["e"]


def prep_checks():
    out = []
    for k, im in enumerate(CHECKS):
        tw = 640 if im.size[0] > im.size[1] else 440
        r = tw / im.size[0]; th = int(im.size[1] * r)
        if th > 800:
            r = 800 / im.size[1]; th = 800; tw = int(im.size[0] * r)
        sm = im.resize((tw, th), Image.LANCZOS)
        b = 10
        cd = Image.new("RGBA", (tw + 2 * b, th + 2 * b), (255, 255, 255, 255)); cd.paste(sm, (b, b))
        mk = Image.new("L", cd.size, 0); ImageDraw.Draw(mk).rounded_rectangle([0, 0, cd.size[0] - 1, cd.size[1] - 1], 28, fill=255); cd.putalpha(mk)
        rot = cd.rotate([-7, 6, -4, 8, -5, 3, -2][k % 7], resample=Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", (rot.size[0] + 120, rot.size[1] + 120), (0, 0, 0, 0))
        blk = Image.new("RGBA", rot.size, (10, 5, 0, 255)); blk.putalpha(rot.split()[3].point(lambda v: int(v * 0.6)))
        sh.paste(blk, (60, 80)); sh = sh.filter(ImageFilter.GaussianBlur(26)); sh.alpha_composite(rot, (60, 60))
        out.append(sh)
    return out


CHK_IMGS = prep_checks()
CHK_POS = [(370, 1190), (710, 1230), (410, 1310), (690, 1300), (470, 1250), (560, 1380), (610, 1270)]


def draw_checks(front, t):
    if not (CHK_T0 - 0.05 <= t < CHK_T1 + 0.3):
        return
    for k, im in enumerate(CHK_IMGS[:7]):
        tin = CHK_T0 + k * 0.25
        if t < tin:
            continue
        p = ease_out((t - tin) / 0.25)
        q = ease_io((t - CHK_T1) / 0.3) if t > CHK_T1 else 0
        sc = (0.6 + 0.4 * p) * (1 - 0.3 * q)
        im2 = im.resize((int(im.size[0] * sc), int(im.size[1] * sc)), Image.BILINEAR)
        im2 = alpha_mul(im2, p * (1 - q))
        if p < 1:
            im2 = im2.filter(ImageFilter.GaussianBlur((1 - p) * 10))
        cx, cy = CHK_POS[k]
        cy += int((1 - p) * 80 + q * 60)
        comp(front, im2, cx - im2.size[0] // 2, cy - im2.size[1] // 2)


# CTA arrow (hand-drawn curve pointing down-right toward comments)
def draw_arrow(front, t):
    t0 = WORDS[-1]["s"]
    if t < t0:
        return
    p = ease_out((t - t0) / 0.5)
    d = ImageDraw.Draw(front)
    pts = [(820 + 60 * math.sin(s * 2.2) * (1 - s) + 40 * s, 540 + 260 * s) for s in np.linspace(0, p, 30)]
    if len(pts) > 1:
        d.line(pts, fill=(255, 240, 220, 230), width=6, joint="curve")
    if p > 0.95:
        x, y = pts[-1]
        d.line([(x - 26, y - 22), (x, y), (x + 22, y - 28)], fill=(255, 240, 220, 230), width=6, joint="curve")


# ------------------------------------------------------------------ frame fx
def load_mask(i):
    p = f"{ROOT}/masks/{min(i + 1, 967):04d}.png"
    m = Image.open(p).resize((W, H), Image.BILINEAR)
    return np.asarray(m, dtype=np.float32)[..., None] / 255.0


def flash_on(t):
    """white flashback blinking on the right figure (ақша таппайтын)"""
    if t >= CUT:
        return 0.0
    if t < WHITE_END:
        return 1.0  # source already white here: keep as is
    f = int(t * FPS)
    # irregular flash rhythm: 2-frame flashes, denser at first
    pat = [1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    return float(pat[f % len(pat)])


def scene_a(frame, mask, t):
    return frame.astype(np.float32)  # hook footage untouched: original white silhouette -> blink -> normal
    fr = frame.astype(np.float32)
    m = mask[..., 0].copy()
    white_src = (fr.mean(2) > 236) if t < WHITE_END + 0.1 else np.zeros(m.shape, bool)
    right = np.zeros_like(m); right[:, 545:] = m[:, 545:]
    right = np.maximum(right, white_src.astype(np.float32))
    R = Image.fromarray((right * 255).astype(np.uint8))
    fl = flash_on(t)
    if fl > 0:
        rm = np.asarray(R.filter(ImageFilter.GaussianBlur(1.5)), np.float32)[..., None] / 255.0
        fr = fr * (1 - rm * 0.96) + 252 * rm * 0.96
        halo = np.asarray(R.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(28)), np.float32)[..., None] / 255.0
        halo = np.clip(halo - rm, 0, 1) * 0.55
        fr = fr * (1 - halo) + 255 * halo
    return fr


def whip(arr, strength):
    """horizontal motion blur for the cut transition"""
    if strength <= 0:
        return arr
    n = int(4 + strength * 10); step = int(6 + strength * 14)
    acc = np.zeros_like(arr, dtype=np.float32)
    for k in range(-n, n + 1):
        acc += np.roll(arr, k * step // 2, axis=1)
    return acc / (2 * n + 1)


HL = []
for c in CARDS:
    for ln in c["lines"]:
        for w in ln:
            if w["style"] in ("B", "A", "N") and w["size"] > 150 and w["t"] > CUT and w is ln[0] and ln is c["lines"][[len(l) for l in c["lines"]].index(len(ln))]:
                HL.append(w["t"])


def zoom_at(t):
    return 1.0
    if t < CUT:
        return 1.0
    z = 1.0 + 0.05 * min(1, (t - CUT) / (DUR - CUT))
    for h in HL:
        p = t - h + 0.05
        if 0 <= p < 0.9:
            z += 0.06 * (ease_out(p / 0.12) if p < 0.12 else 1 - ease_io((p - 0.12) / 0.78) * 0.6)
    return z


def zoom_img(arr, z, cy=0.38):
    if abs(z - 1) < 1e-3:
        return arr
    h, w = arr.shape[:2]; nw, nh = int(w / z), int(h / z)
    x0 = (w - nw) // 2; y0 = int((h - nh) * cy)
    if arr.ndim == 3 and arr.shape[2] == 1:
        im = Image.fromarray((arr[y0:y0 + nh, x0:x0 + nw, 0] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
        return np.asarray(im, np.float32)[..., None] / 255.0
    return np.asarray(Image.fromarray(arr[y0:y0 + nh, x0:x0 + nw].astype(np.uint8)).resize((w, h), Image.BILINEAR)).astype(np.float32)


yy, xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.26 * np.clip(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2, 0, 1))[..., None].astype(np.float32)
del yy, xx


def over(base, layer):
    a = layer[..., 3:4] / 255.0
    return base * (1 - a) + layer[..., :3] * a


def render_frame(i, frame):
    t = i / FPS
    mask = load_mask(i)
    if t < CUT:
        fr = scene_a(frame, mask, t)
        person = mask
    else:
        z = zoom_at(t)
        fr = zoom_img(frame, z); person = zoom_img(mask, z)
    back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    front = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dust_cards = []
    for c in CARDS:
        if not (c["t0"] - 0.1 <= t < c["end"]):
            continue
        if c["exit"] == "dust" and t >= c["xs"]:
            dust_cards.append(c); continue
        ex_q = 0.0
        if t >= c["xs"]:
            ex_q = min(1, (t - c["xs"]) / EXIT_DUR[c["exit"]])
        if c["kind"] == "roll":
            draw_roll(front, c, t, ex_q); continue
        if c["kind"] == "stair":
            draw_stair(front, c, t, ex_q); continue
        for ln in c["lines"]:
            for w in ln:
                tgt = front
                draw_word(tgt, w, t, ex_q, c["exit"])
    draw_checks(front, t)
    draw_arrow(front, t)
    b = np.asarray(back, np.float32)
    fa = np.asarray(front, np.float32).copy()
    for c in dust_cards:
        dust_frame(c, t, fa)
    out = over(fr, b)
    out = out * (1 - person) + fr * person
    out = over(out, fa)
    # whip transition around the cut
    dtc = abs(t - CUT)
    if dtc < 0.12:
        out = whip(out, 1 - dtc / 0.12)
    out = out * VIG
    out += rng.normal(0, 3.0, (H // 2, W // 2, 1)).repeat(2, 0).repeat(2, 1)
    return np.clip(out, 0, 255).astype(np.uint8)


def frames_reader():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)


if __name__ == "__main__":
    if PREVIEW:
        os.makedirs(os.path.join(ROOT, "prev"), exist_ok=True)
        for t in [float(x) for x in PREVIEW.split(",")]:
            i = int(round(t * FPS))
            fr = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{i / FPS:.4f}", "-i", SRC, "-frames:v", "1", "-vf", f"scale={W}:{H}",
                                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            fr = np.frombuffer(fr, np.uint8).reshape(H, W, 3)
            Image.fromarray(render_frame(i, fr)).resize((360, 640)).save(f"{ROOT}/prev/{t:05.2f}.jpg")
        sys.exit()
    out = sys.argv[1]
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i, fr in enumerate(frames_reader()):
        if i / FPS >= DUR:
            break
        enc.stdin.write(render_frame(i, fr).tobytes())
        if i % 60 == 0:
            print("frame", i, flush=True)
    enc.stdin.close(); enc.wait(); print("done")
