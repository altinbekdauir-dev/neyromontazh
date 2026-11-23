"""Привязка слов сценария ко времени в аудио (без интернета, без моделей).

Как работает: ищет паузы в речи и раскладывает слова между ними пропорционально
числу слогов (гласных). Концы предложений «прилипают» к ближайшим паузам.
Для спорных мест можно задать якоря вручную (--anchors), например после
проверки распознаванием речи на коротком куске.

Пример:
  python montage/tools/align.py --text script.txt --audio input/source.mov \
      --out words.json --pauses            # сначала посмотреть паузы
  python montage/tools/align.py --text script.txt --audio input/source.mov \
      --out words.json --anchors '{"8": [4.24, 4.36]}'
"""
import argparse, json, subprocess, sys
import numpy as np

V = set("аәеёиоөуұүыіэюяАӘЕЁИОӨУҰҮЫІЭЮЯaeiouyAEIOUY")
NUM_SYL = {}  # можно дополнить: {"1993": 9, "18": 3}


def syl(w):
    if w in NUM_SYL:
        return NUM_SYL[w]
    if any(c.isdigit() for c in w):
        return 2 * sum(c.isdigit() for c in w)
    return max(1, sum(c in V for c in w))


def envelope(audio):
    from scipy.signal import butter, sosfilt
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    b = sosfilt(butter(4, [250, 3500], "bandpass", fs=16000, output="sos"), a)
    hop = 160
    env = np.array([np.sqrt((b[i * hop:(i + 1) * hop] ** 2).mean()) for i in range(len(b) // hop)])
    db = 20 * np.log10(env + 1e-9)
    return db - db.max()


def find_pauses(db, th=-32, min_len=0.12):
    low = db < th; out = []; i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            if (j - i) / 100 >= min_len:
                out.append((i / 100, j / 100))
            i = j
        else:
            i += 1
    return out


def align(words, db, anchors, start, end):
    act = (db > -32).astype(float)
    S = [syl(w) for w in words]; N = len(words)
    keys = sorted(anchors); segs = []; pw, pt = 0, start
    for k in keys:
        segs.append((pw, k, pt, anchors[k][0])); pw = k + 1; pt = anchors[k][1]
    segs.append((pw, N - 1, pt, end)); out = [None] * N
    for a, b, t0, t1 in segs:
        fr = np.arange(int(t0 * 100), int(t1 * 100)); w = act[fr] + 0.15
        cum = np.concatenate([[0], np.cumsum(w)]); tot = cum[-1]
        ss = S[a:b + 1]; ct = sum(ss) or 1; c = 0
        for i, s in zip(range(a, b + 1), ss):
            ts = fr[0] / 100 + np.searchsorted(cum, c / ct * tot) / 100; c += s
            te = fr[0] / 100 + np.searchsorted(cum, c / ct * tot) / 100
            out[i] = [round(float(ts), 2), round(float(te), 2)]
    return out


def auto_anchors(words, db, pauses, start, end, iters=8):
    punct = [i for i, w in enumerate(words) if w[-1] in ",.?!—" and i < len(words) - 1]
    anchors = {}
    for _ in range(iters):
        t = align(words, db, anchors, start, end); new = {}
        for i in punct:
            best = min(pauses, key=lambda p: abs(p[0] - t[i][1]), default=None)
            if best and abs(best[0] - t[i][1]) < 1.2:
                new[i] = best
        inv = {}
        for i, p in new.items():
            if p not in inv or abs(t[i][1] - p[0]) < abs(t[inv[p]][1] - p[0]):
                inv[p] = i
        anchors = {i: p for p, i in inv.items()}
    return anchors


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True); ap.add_argument("--audio", required=True)
    ap.add_argument("--out", default="words.json"); ap.add_argument("--anchors")
    ap.add_argument("--pauses", action="store_true", help="только показать паузы и выйти")
    a = ap.parse_args()
    words = [w for w in open(a.text, encoding="utf-8").read().split() if w not in ("—", "-")]
    db = envelope(a.audio); pauses = find_pauses(db)
    if a.pauses:
        print(" ".join(f"{s:.2f}-{e:.2f}" for s, e in pauses)); sys.exit()
    start = float(np.argmax(db > -25)) / 100; end = float(len(db) - np.argmax(db[::-1] > -25)) / 100
    anchors = {int(k): tuple(v) for k, v in json.loads(a.anchors).items()} if a.anchors else auto_anchors(words, db, pauses, start, end)
    t = align(words, db, anchors, start, end)
    json.dump([{"w": w, "s": s, "e": e} for w, (s, e) in zip(words, t)], open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    for i, w in enumerate(words):
        if w[-1] in ",.?!" or i in anchors:
            print(t[i], w, "<- пауза" if i in anchors else "")
