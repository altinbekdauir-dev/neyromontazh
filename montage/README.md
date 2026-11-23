# Монтаж рилс кодом

Конвейер, на котором сделаны ролики «Ақша табатын ИИ креатор» и «История тенге».
Стиль и правила — в [STYLE.md](STYLE.md).

## Структура
```
montage/
  STYLE.md                 паспорт стиля (утверждённые правки)
  tools/align.py           слова сценария → время (words.json)
  tools/mix.py             звук на акцентах, 70% от голоса, лимитер
  examples/ai_creator/     титры над головой, хук с силуэтом, чеки
  examples/tenge/          экран поделён: эксперт + карточки, карта, материалы
  fetch_fonts.sh           бесплатные шрифты (Montserrat и др.)
  requirements.txt
```
Рабочая папка `work/` (в git не попадает): `work/input/` исходник, `work/fonts/` шрифты, `work/sfx/` звуки, `work/img/` фото, `work/clips/` нарезка видео, `work/out/` готовое. Скрипты берут пути от `MONTAGE_ROOT` (по умолчанию текущая папка), поэтому запускай всё из `work/`.

## Быстрый старт
```bash
pip install -r montage/requirements.txt      # + нужен ffmpeg
mkdir -p work && cd work
bash ../montage/fetch_fonts.sh               # Montserrat, Inter, Oswald, Playfair -> work/fonts
# положить файлы заказчика: fonts/BebasNeueBold.otf, fonts/GoodVibesPro.ttf, sfx/apple.mp3, input/source.mov
python ../montage/tools/align.py --text script.txt --audio input/source.mov --out words.json
PREVIEW="2,10,20" python ../montage/examples/tenge/render.py          # превью кадров -> prev/
python ../montage/examples/tenge/render.py video_noaudio.mp4
python ../montage/tools/mix.py --voice input/source.mov --sfx sfx/apple.mp3 --appear appear.json --out mix.wav
ffmpeg -i video_noaudio.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest out/reel.mp4
```

## Как устроен рендер
- Кадры исходника читаются через ffmpeg, всё рисуется в Python (Pillow + numpy) и пишется обратно в ffmpeg.
- **Титры:** список `card([[S(), S()], [B()], [S()]])` — строки карточки; `S` мелкие слова, `B` крупное, `A` крупное бежевое, `N` тёплое свечение, `G` курсив Good Vibes. Каждый вызов забирает следующие слова сценария по порядку.
- **Графика:** список `PANELS = [(t_in, t_out, [shots])]`; shot — `clip` (нарезка видео в `clips/<имя>/`), `img` (фото из `img/`), или своя карточка (`map`, `year`, `months`, `rate`, `date`, `sub`…). Нарезка клипа: `ffmpeg -ss START -t DUR -i src.mp4 -vf "fps=30,scale=880:560:force_original_aspect_ratio=increase,crop=880:560" clips/имя/%04d.jpg`.
- Пути внутри скриптов сделаны относительно `MONTAGE_ROOT`; при переносе на новый ролик проверь их и время слов (`wt(i)`).
- Маска человека (если текст должен уходить за голову): `rembg` модель `u2net_human_seg`, кадры в `masks/`.

Примеры — это рабочий код конкретных роликов, а не универсальная программа: для нового ролика копируй ближайший пример и меняй сценарий, карточки и материалы.
