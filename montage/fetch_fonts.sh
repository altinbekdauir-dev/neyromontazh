#!/usr/bin/env bash
# Бесплатные шрифты (SIL OFL) из репозитория Google Fonts. Шрифты заказчика сюда не входят.
set -e
mkdir -p fonts && cd fonts
B=https://raw.githubusercontent.com/google/fonts/main/ofl
get(){ curl -sfL "$B/$1" -o "$2" && echo "ok $2" || echo "FAIL $2"; }
get "montserrat/Montserrat%5Bwght%5D.ttf" "Montserrat[wght].ttf"
get "montserrat/Montserrat-Italic%5Bwght%5D.ttf" "Montserrat-Italic[wght].ttf"
get "inter/Inter%5Bopsz%2Cwght%5D.ttf" "Inter[opsz,wght].ttf"
get "oswald/Oswald%5Bwght%5D.ttf" "Oswald[wght].ttf"
get "playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf" "PlayfairDisplay-Italic[wght].ttf"
get "ibmplexmono/IBMPlexMono-Regular.ttf" "IBMPlexMono-Regular.ttf"
ls ../fonts | grep -q BebasNeueBold || echo "!! Нет fonts/BebasNeueBold.otf — попроси файл у заказчика"
ls ../fonts | grep -q GoodVibesPro || echo "!! Нет fonts/GoodVibesPro.ttf — попроси файл у заказчика"
