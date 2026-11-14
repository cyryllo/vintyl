#!/bin/sh
# Tworzy wszystkie pliki ikony i logo Vintyl z jednego źródła:
# assets/ikona/vintyl.svg.
#
# Wynik:
#   assets/ikona/vintyl-<rozmiar>.png    16, 32, 48, 64, 128, 256, 512 px
#   assets/ikona/vintyl.ico              ikona dla Windows (16–256 px)
#   assets/logo/vintyl-logo-{light,dark}.svg / .png   ikona z napisem, 1400x400
#
# Potrzebne: inkscape (rysowanie SVG i zamiana napisów na krzywe),
# ImageMagick (plik .ico) oraz czcionka Noto Sans.
# Napisy w logo są zamieniane na krzywe, żeby logo wyglądało tak samo
# na komputerze bez czcionki Noto Sans (np. na stronie WWW).
set -eu
cd "$(dirname "$0")/.."

ICON=assets/ikona/vintyl.svg
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# --- ikona w kilku rozmiarach ---------------------------------------------
for s in 16 32 48 64 128 256 512; do
    inkscape "$ICON" -w "$s" -h "$s" -o "assets/ikona/vintyl-$s.png" 2>/dev/null
done
magick assets/ikona/vintyl-16.png assets/ikona/vintyl-32.png assets/ikona/vintyl-48.png \
       assets/ikona/vintyl-64.png assets/ikona/vintyl-128.png assets/ikona/vintyl-256.png \
       assets/ikona/vintyl.ico

# --- logo: ikona po lewej, nazwa i podtytuł po prawej ----------------------
# Układ jak w logo Millwise: ikona 512 px pomniejszona do 0,61,
# nazwa Noto Sans Bold 176 px, podtytuł Noto Sans Medium 54 px.
# Treść ikony (bez nagłówka <svg>) wstawiamy do grupy, żeby nie powielać rysunku.
BODY=$(sed -e '1,/<svg /d' -e '/<\/svg>/d' "$ICON")

make_logo() {   # $1 = light|dark, $2 = kolor nazwy, $3 = kolor podtytułu
    cat > "$TMP/logo-$1.svg" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!-- Vintyl — logo (ikona + napis), wersja $1. Plik tworzy tools/make_icons.sh. -->
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="400" viewBox="0 0 1400 400">
  <g transform="translate(40 44) scale(0.61)">
$BODY
  </g>
  <text x="408" y="232" style="font-weight:700;font-size:176px;font-family:'Noto Sans';letter-spacing:-3px;fill:$2">Vintyl</text>
  <text x="414" y="314" style="font-weight:500;font-size:54px;font-family:'Noto Sans';letter-spacing:1px;fill:$3">Software for vinyl cutters</text>
</svg>
EOF
    inkscape "$TMP/logo-$1.svg" --export-text-to-path --export-plain-svg \
             -o "assets/logo/vintyl-logo-$1.svg" 2>/dev/null
    inkscape "assets/logo/vintyl-logo-$1.svg" -w 1400 -h 400 \
             -o "assets/logo/vintyl-logo-$1.png" 2>/dev/null
}

make_logo light "#141b2d" "#5b6578"   # na jasne tło
make_logo dark  "#f2f4f7" "#9aa7bd"   # na ciemne tło

echo "Gotowe: assets/ikona i assets/logo"
