"""Саунд-дизайн по правилам канала: звук только на акцентных словах и появлении графики.

Громкость: каждый звук = 70% громкости голоса (на 30% тише). Звуки на чеках/скриншотах — 40%.
Сверху лимитер, чтобы не было перегруза.

Пример:
  python montage/tools/mix.py --voice input/source.mov --sfx sfx/apple.mp3 \
      --appear appear.json --styles A --extra 4.5,8.0 --out mix.wav
  ffmpeg -i video_noaudio.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest out.mp4
"""
import argparse, json, subprocess
import numpy as np, soundfile as sf

SR = 48000


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True); ap.add_argument("--sfx", required=True)
    ap.add_argument("--appear", help="appear.json из рендера (text, style, t)")
    ap.add_argument("--styles", default="A", help="стили слов, на которые ставить звук, через запятую")
    ap.add_argument("--words", default="", help="конкретные слова (как на экране), через запятую")
    ap.add_argument("--extra", default="", help="доп. моменты в секундах, через запятую (появление карточек)")
    ap.add_argument("--quiet", default="", help="моменты для тихих звуков (чеки, скриншоты) — 40%")
    ap.add_argument("--trim", type=float, default=0.385, help="сдвиг начала звука до удара (для Apple_2 = 0.385)")
    ap.add_argument("--out", default="mix.wav")
    a = ap.parse_args()
    voice = load(a.voice); N = len(voice); vm = voice.mean(1); h = int(0.05 * SR)
    vw = np.array([np.sqrt((vm[i:i + h] ** 2).mean()) for i in range(0, N - h, h)])
    target = np.percentile(vw[vw > np.percentile(vw, 40)], 75) * 0.7
    fx = load(a.sfx).mean(1)[int(a.trim * SR):]
    f = int(0.004 * SR); fx[:f] *= np.linspace(0, 1, f)
    win = max(np.sqrt((fx[i:i + h] ** 2).mean()) for i in range(0, max(1, len(fx) - h), h // 4))
    bus = np.zeros(N); times = []

    def tap(t, rel=1.0):
        i = max(0, int((t - 0.05) * SR)); n = min(len(fx), N - i)
        bus[i:i + n] += fx[:n] * target / win * rel

    if a.appear:
        styles = set(a.styles.split(",")); words = set(w for w in a.words.split(",") if w)
        for w in json.load(open(a.appear, encoding="utf-8")):
            if w["style"] in styles or w["text"] in words:
                if all(abs(w["t"] - x) > 0.3 for x in times):
                    tap(w["t"]); times.append(w["t"])
    for x in [float(v) for v in a.extra.split(",") if v]:
        if all(abs(x - y) > 0.35 for y in times):
            tap(x, 0.8); times.append(x)
    for x in [float(v) for v in a.quiet.split(",") if v]:
        tap(x, 0.4)
    mix = voice + np.stack([bus, bus], 1)
    sf.write("_mix_raw.wav", mix, SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "_mix_raw.wav", "-af",
                    "alimiter=limit=0.95:attack=1:release=40:level=disabled", "-ar", str(SR), a.out], check=True)
    print("звуков:", len(times))
