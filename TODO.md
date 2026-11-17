# Do zrobienia

Lista roboczych zadań Vintyla. Zrobione rzeczy przechodzą do
[CHANGELOG.md](CHANGELOG.md).

## Następny krok

- [ ] **Kolor wypełnienia.** Wypełnienie może mieć inny kolor niż kontur
  kształtu, żeby rysował je inny pisak: np. czarny kontur i różowe
  wypełnienie. Teraz wypełnienie zawsze idzie w kolorze swojego kształtu.
  W oknie Wypełnienie i przy wiaderku w panelu Kolory: wybór koloru projektu
  (albo „jak kształt”); przy Starcie wypełnienie rysuje się razem z tym
  kolorem, do którego należy.

## Funkcje

- [ ] **Wektoryzacja obrazka** (PNG/JPG → kontury do cięcia), przeniesiona
  z Kerfly: `kerfly/core/trace.py` (próg czerni, kontury z dziurami,
  usuwanie drobnych plamek, upraszczanie, wygładzanie w krzywe; potrzebuje
  tylko Pillow). Z nagłówkiem o autorach i licencji. Sprawdzić najpierw
  aktualną wersję w Kerfly.
- [ ] **Łączenie liter w napisie** jednym przyciskiem: przy czcionkach
  pisanych litery zachodzą na siebie i nóż tnąłby w środku napisu. Suma
  kształtów już jest; brakuje „połącz napis” (litery w jeden kontur).
- [ ] **Układanie elementów na folii** jak najciaśniej, żeby oszczędzać
  folię (z odstępem, obracane, gdy to pomaga). W Kerfly jest w planach
  (ROADMAP.md, „Nesting”, wersja 2.0: najpierw po prostokątach — MaxRects,
  które mają już generatory pudełek — potem po prawdziwych konturach,
  biblioteka sparrow/spyrrow). Przenieść, gdy Kerfly to zrobi, albo zacząć
  od prostokątów.
- [ ] **Cięcie perforowane** (linia przerywana: odcinek cięty, odcinek
  nie) do papieru i kartonu: zginanie, odrywanie. Przełącznik na element,
  długość cięcia i przerwy.

## Paczki

- [ ] **Pakiet .deb** (Debian, Ubuntu, Mint) obok AppImage.
- [ ] **Flatpak** (Flathub); dostęp do /dev/usb/lp* i portów szeregowych
  trzeba sprawdzić, bo Flatpak domyślnie ich nie daje.

## Później

- [ ] **Dopracowanie kolorów (0.9).** Uwagi po testach właściciela, gdy
  będzie na nie czas.
- [ ] **Lewy panel z kolorami.** Przy oknie wysokim na 768–860 px, gdy jest
  panel Kolory, lista Elementów pokazuje tylko 2 wiersze (resztę widać po
  przewinięciu panelu). Do decyzji, czy to poprawiać.

## Na koniec

- [ ] **Wersja 1.0**, kiedy właściciel uzna, że program jest gotowy.
