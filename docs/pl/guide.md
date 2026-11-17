---
layout: default
title: Instrukcja obsługi
lang: pl
other_lang: guide.html
---
{% assign img = '/screenshots/pl/' | relative_url %}

# Instrukcja obsługi Vintyla

Vintyl steruje z Linuksa ploterami tnącymi z nożem wleczonym: układa Twoje
projekty na obrazie materiału, pozwala je rysować i zmieniać, a potem wysyła
zadanie do plotera. Instrukcja dotyczy wersji 0.9.0.

> Nic nie trafia do plotera, dopóki nie potwierdzisz tego na liście
> kontrolnej. Przed pierwszym cięciem nowego materiału wytnij test noża.

- [1. Instalacja i pierwsze uruchomienie](#s1)
- [2. Okno programu](#s2)
- [3. Ploter](#s3)
- [4. Materiały](#s4)
- [5. Rysowanie i edycja](#s5)
- [6. Otwieranie i zapisywanie plików](#s6)
- [7. Układanie projektu](#s7)
- [8. Cięcie](#s8)
- [9. Rysowanie pisakiem](#s9)
- [10. Kolory](#s10)
- [11. Ustawienia](#s11)
- [12. Skróty klawiszowe](#s12)
- [13. Gdy coś nie działa](#s13)

<a id="s1"></a>

## 1. Instalacja i pierwsze uruchomienie

1. Pobierz AppImage z
   [wydań]({{ site.repo }}/releases/latest). To jeden plik ze wszystkim w
   środku, działa na większości 64-bitowych Linuksów.
2. Nadaj mu prawo uruchamiania i uruchom:

   ```bash
   chmod +x Vintyl-*-x86_64.AppImage
   ./Vintyl-*-x86_64.AppImage
   ```

   Vintyl raz zapyta, czy dodać go do menu aplikacji (później także
   Pomoc → Dodaj Vintyl do menu aplikacji).
3. **Pozwól swojemu kontu wysyłać do plotera.** W Linuksie ploter to plik
   urządzenia i używać go mogą tylko członkowie jego grupy. Dołącz do grupy
   raz, potem wyloguj się i zaloguj ponownie:

   ```bash
   sudo usermod -aG lp $USER        # ploter podłączony jako drukarka USB
   sudo usermod -aG dialout $USER   # port szeregowy (Arch, Manjaro: uucp)
   ```

   Pomoc → Dostęp do plotera pokazuje to samo z przyciskiem do skopiowania
   poleceń i mówi, czy możesz teraz używać wybranego portu.
4. Podłącz ploter, włącz go i wybierz go w polu **Ploter** w lewym panelu.
   Zielona kropka znaczy, że jest gotowy; żółta ramka mówi, czego brakuje,
   i prowadzi do pomocy.
5. Wybierz **Materiał** (na początek folię winylową).

<a id="s2"></a>

## 2. Okno programu

![Okno Vintyla]({{ img }}main-window.png)

- **Wstążka** na górze: Plik, Edycja, Element, Przekształć, Wyrównaj,
  Kształty i Widok. Przyciski, które potrzebują zaznaczenia, są bez niego
  szare; każdy ma podpowiedź.
- **Pasek zaznaczenia** pod nią: typ i nazwa zaznaczonego elementu, jego
  położenie (X wzdłuż materiału, Y w poprzek) i wymiary (z kłódką, która
  trzyma proporcje), kąt obrotu, pola jego rodzaju (promień narożników
  prostokąta, boki wielokąta, czcionka tekstu) i **Tnij ten element**. Bez
  zaznaczenia pokazuje podpowiedź, a przy miarce zmierzoną długość.
- **Lewy panel**:
  - **Elementy**: lista w kolejności cięcia, każdy z numerem, typem i
    nożyczkami (kliknij je, żeby elementu nie ciąć). Strzałki przesuwają
    zaznaczony wcześniej albo później. Prawy przycisk otwiera to samo menu
    co na arkuszu.
  - **Ploter**: ploter, jego stan, narzędzie (nóż albo pisak) i materiał,
    z naciskiem i prędkością do ustawienia.
  - **Zadanie**: długość cięcia, przejazdy i przełączniki zadania.
  - Na dole, zawsze na wierzchu: **Start**, **Zapisz .hpgl** i **Test noża**.
- **Arkusz**: materiał tak, jak leży w ploterze, widziany z góry.
  **Punkt zerowy** (0, 0) to pomarańczowy krzyżyk w prawym dolnym rogu, tam
  ploter zaczyna (klawisz Origin); X biegnie w górę wzdłuż materiału, Y w
  lewo w poprzek. Linijki w mm, szerokość cięcia u góry, przyciski
  powiększenia w prawym dolnym rogu; kółko myszy powiększa, środkowy
  przycisk przesuwa widok.
- **Pasek narzędzi** po prawej. Mały trójkąt w rogu przycisku znaczy, że
  otwiera zestaw narzędzi.

  ![Zestaw narzędzi]({{ img }}tool-set.png)

<a id="s3"></a>

## 3. Ploter

Ploter wybierasz w lewym panelu. **Ustawienia plotera** (przycisk obok
albo Ploter → Ustawienia plotera) mają dla każdego plotera:

![Ustawienia plotera]({{ img }}cutter-settings.png)

- **Maszyna**: nazwa, szerokość cięcia, długość (0: rolka).
- **Połączenie**: drukarka USB (`/dev/usb/lp…`) albo port szeregowy, port
  (Szukaj pokazuje znalezione urządzenia i to, czy masz do nich dostęp), a
  dla portu szeregowego jego prędkość i kontrolę przepływu.
- **Prędkość i nacisk**: czy wysyła je komputer. Plotery VEVOR i Seiki
  biorą je tylko z panelu, więc to jest wyłączone.
- **Polecenia**: HPGL albo DMPL, jednostki na mm i osie (zamiana,
  odwrócenie), gdyby ploter ciął obrócony albo w lustrze.
- **Nóż**: przesunięcie noża (o ile czubek ostrza jest za osią oprawki) i
  nadcięcie. Vintyl wlicza je w ścieżkę noża; na ploterze nic się dla nich
  nie ustawia.

Wbudowane plotery można zmieniać: zmiany są zapisywane jako Twoja kopia, a
**Przywróć ustawienia fabryczne** przywraca oryginał. **Nowy ploter (kopia)**
zaczyna własny profil od pokazanego.

<a id="ostrza"></a>

### Ostrza i przesunięcie noża

Kąt ostrza mówi, jak gruby materiał tnie; jego **przesunięcie** (o ile
czubek jest za osią oprawki) jest Vintylowi potrzebne, żeby ostro brać
narożniki. Przesunięcie podaje producent ostrza: jeśli jest na opakowaniu,
użyj tej wartości. W przeciwnym razie:

| Ostrze | Przesunięcie noża | Do czego |
|---|---|---|
| 45° (zwykłe) | 0,25 mm | zwykła folia, flex (termotransferowa), „do wszystkiego” |
| 60° | 0,50 mm | grube materiały: folia odblaskowa, do piaskowania, flock, magnetyczna, karton, folia grubsza niż 3 mil (0,08 mm) |
| 60°, do bardzo grubych | 1,00 mm | bardzo grube: karton, magnetyczna, do piaskowania |
| 30° (cienkie folie) | ok. 0,25 mm | cienkie folie i drobne detale |

Wiersze 45° i 60° pochodzą od Rolanda (Cutter Blade Reference Guide, 2017:
ostrza ZEC-U5032, ZEC-U1005, USA-C145-X jako 45°/0,25; ZEC-U3050 jako
60°/0,50; ZEC-U3100 jako 60°/1,00). Wiersz 30° pochodzi od sprzedawców
ostrzy i jest tylko punktem wyjścia. Ostrza innych producentów mają te
same kąty, ale ich przesunięcie może się różnić: wytnij test noża.

Gdzie to ustawić: wartość plotera jest w ustawieniach plotera
(Przesunięcie noża, 0,25 mm dla dołączonego ostrza 45°). Materiał, który
potrzebuje innego ostrza, może mieć własną: w oknie materiałów pola Ostrze
i Przesunięcie noża (puste: wartość plotera). Wbudowana folia odblaskowa
ma ostrze 60° z przesunięciem 0,50 mm; jeśli Twoje ostrze 60° ma inne,
zmień je tam.

**Jak czytać narożniki** (Roland): zaokrąglone narożniki to za małe
przesunięcie; małe chorągiewki wystające na narożnikach to za duże.

| Ploter | Stan |
|---|---|
| VEVOR KI-375A | przetestowany: tnie czysto |
| Seiki SK-870T | przetestowany: tnie czysto |
| VEVOR 870 mm | profil gotowy, ta sama płyta |
| VEVOR / Seiki, inny model | ustaw szerokość cięcia; powinien działać tak samo |

Te plotery były używane w trybie drukarki USB. Ich drugi tryb,
**Virtual COM** (port szeregowy, inny sterownik), jest przygotowany w
profilach, ale nie był jeszcze sprawdzony na ploterze.

<a id="s4"></a>

## 4. Materiały

![Okno materiałów]({{ img }}materials.png)

Materiał mówi, jak go ciąć (albo po nim rysować): narzędzie, **nacisk i
prędkość dla każdego plotera**, ostrze, przesunięcie noża i nadcięcie
(puste: wartości plotera), lustro, ramkę do wybierania i notatkę
pokazywaną przed Startem. Wybranie materiału ustawia narzędzie i
przełączniki zadania.

Wbudowane, jako wartości startowe dla ploterów VEVOR i Seiki, wszystkie
przy 300 mm/s:

| Materiał | Mały KI-375A | Plotery 870 mm |
|---|---|---|
| Folia winylowa | 50 g | 80 g |
| Folia termotransferowa (flex), w lustrze | 60 g | 120 g |
| Folia odblaskowa, ostrze 60° | 40 g | 80 g |
| Papier, cienkopis (pisak) | 35 g | 70 g |
| Karton, marker (pisak) | 35 g | 70 g |

Plotery różnią się nawet przy tej samej płycie: sprawdź wartości testem
noża i wpisz własne w materiale. Okno materiałów otwiera przycisk obok
pola Materiał; **dla:** wybiera ploter, którego wartości widzisz. **Test
noża z tymi wartościami** od razu wycina test.

<a id="s5"></a>

## 5. Rysowanie i edycja

Wybierz narzędzie po prawej (albo naciśnij jego klawisz) i przeciągnij na
arkuszu:

- **Kształty**: prostokąt (R, z promieniem narożników w pasku
  zaznaczenia), elipsa (E), wielokąt (P, liczba boków w pasku).
- **Gotowe**: gwiazda, serce, pierścień, zaokrąglony prostokąt, strzałka,
  krzyżyk, kropla, koło zębate i kod QR. Każdy otwiera małe okno z
  rysunkiem i wymiarami; **Zachowaj proporcje** zmienia pozostałe wymiary
  razem z jednym.
- **Linie**: linia łamana (L: klikaj narożniki; pierwszy zamyka kształt),
  linia (Shift+L), pióro (B: klik to narożnik, przeciągnięcie to krzywa),
  odręcznie (F).
- **Tekst** (T): kliknij, gdzie ma się zaczynać, i pisz w pasku
  zaznaczenia; dowolna zainstalowana czcionka, pogrubienie, kursywa, odstęp
  liter. **Tekst po ścieżce** układa zaznaczony tekst wzdłuż innego
  zaznaczonego kształtu.
- **Węzły** (N albo dwuklik na kształcie): przeciągaj węzły i uchwyty;
  dwuklik na boku dodaje węzeł; D usuwa, L robi linię, C krzywą, O gładki
  węzeł, Z zamyka albo otwiera, B rozcina.
- **Odsunięcie** (O): obrys o daną odległość na zewnątrz albo do środka;
  **Usuń wewnętrzne otwory** daje pełny podkład pod napis w innym kolorze.
- **Suma, różnica, część wspólna, wykluczenie** (wstążka, Kształty).
- **Wzór z kształtów** (Shift+T): rzędy małych kształtów wewnątrz
  zaznaczonego zamkniętego kształtu, każdy w całości, cięte przed obrysem,
  z podglądem w oknie i na arkuszu.

  ![Wzór z kształtów]({{ img }}pattern-of-shapes.png)
- **Miarka** (M): przeciągnij między dwoma punktami; długość pokaże się w
  pasku zaznaczenia.

Przyciąganie do narożników, środków i krawędzi innych kształtów jest
włączone; przytrzymaj Alt, żeby postawić dowolnie. Siatka (Ctrl+') i jej
odstęp są w ustawieniach.

<a id="s6"></a>

## 6. Otwieranie i zapisywanie plików

- **Otwórz** (Ctrl+O): projekty Vintyla (.vintyl), **SVG** i **DXF**. Plik
  DXF bez jednostek zapyta, czy to milimetry, centymetry czy cale. SVG w
  kilku kolorach otwiera się w swoich kolorach (zobacz [10](#s10)).
- **Zapisz** (Ctrl+S) zapisuje projekt: rysunek, ploter i materiał,
  przełączniki zadania.
- **Zapisz .hpgl** (Ctrl+E) zapisuje plik dla plotera, żeby wyciąć go w
  inny sposób. Projekt w kilku kolorach dostaje osobny plik na każdy kolor
  (`logo-1-Czarny.hpgl`, `logo-2-Różowy.hpgl`…).

<a id="s7"></a>

## 7. Układanie projektu

- Przeciągnij kształt, żeby go przesunąć; przeciągnij kwadraciki, żeby
  zmienić rozmiar (kłódka w pasku zaznaczenia trzyma proporcje); strzałki
  przesuwają po trochu. Dokładne liczby wpisz w pasku zaznaczenia.
- Obrót o 90° (Ctrl+[ i Ctrl+]) albo o dowolny kąt (pole i przycisk w
  pasku zaznaczenia); lustro (Ctrl+M) i odwrócenie (Ctrl+Shift+M).
- **Wyrównaj** i **rozmieść** dwa kształty lub więcej (wstążka, Wyrównaj).
- **Grupuj** (Ctrl+G) kształty, żeby przesuwać je razem.
- **Do 0,0** (Ctrl+Home, wstążka Widok): zaznaczone elementy, a bez
  zaznaczenia cały projekt, jadą razem do punktu zerowego, więc przed nimi
  nie marnuje się folii. Zostaje miejsce na ramkę do wybierania i nóż.

  ![Po „Do 0,0”]({{ img }}to-origin-after.png)
- **Kopie** (Obiekt → Kopie): rzędy wzdłuż i kolumny w poprzek, z odstępem,
  albo tyle kolumn, ile zmieści się w szerokości.
- **Kolejność cięcia** to lista elementów: strzałki obok niej albo prawy
  przycisk → Kolejność cięcia. Kształty wewnętrzne i tak są cięte najpierw.
- Prawy przycisk na kształcie albo na liście otwiera jego menu (kopiuj,
  wytnij, wklej, duplikuj, usuń, grupuj, kolejność cięcia, obrót, lustro,
  Dosuń do punktu 0,0, edytuj węzły, tnij albo nie).

  ![Menu pod prawym przyciskiem na liście elementów]({{ img }}list-menu.png)
- Cofnij (Ctrl+Z) i ponów (Ctrl+Shift+Z) działają dla wszystkiego.

<a id="s8"></a>

## 8. Cięcie

1. Włóż materiał pod rolki dociskowe i ustaw punkt zerowy klawiszem
   **Origin** plotera tam, gdzie ma się zaczynać projekt.
2. Ustaw **nacisk i prędkość** na panelu plotera (materiał pokazuje je pod
   polem Materiał).
3. Sprawdź przełączniki zadania w lewym panelu:
   - **Najpierw kształty wewnętrzne** (włączone): otwory przed obrysem.
   - **Lustro (folia termotransferowa)**: zadanie jest cięte w lustrze, a
     ekran pokazuje projekt tak, jak będzie na koszulce.
   - **Ramka dookoła projektu**, z marginesem: ramka cięta na końcu, do
     wybierania.
4. **Ścieżka noża** (Ctrl+K) pokazuje dokładnie, co zrobi nóż: cięcia w
   kolejności i przejazdy.

   ![Ścieżka noża]({{ img }}knife-path.png)
5. Naciśnij **Start**. Lista kontrolna pokazuje ploter, narzędzie,
   materiał, dużymi cyframi nacisk i prędkość do ustawienia na panelu,
   ostrze i to, co Vintyl wlicza w ścieżkę noża. Sprawdź punkty i naciśnij
   **Tnij**.

   ![Lista kontrolna przed Startem]({{ img }}check-list.png)
6. W czasie wysyłania w miejscu Startu jest **Stop** z procentem wysłanych
   danych. Żeby od razu zatrzymać ploter: Test (pauza) albo Reset na jego
   panelu.

**Test noża.** Przy nowym materiale naciśnij **Test noża**: ploter wytnie
kwadrat 15 mm z trójkątem przy punkcie zerowym. Zdejmij trójkąt: ma zejść
czysto, a podkład nie może być przecięty. Za płytko: większy nacisk; ślady
w podkładzie: mniejszy. Przed projektem przesuń punkt zerowy dalej.

![Test noża]({{ img }}knife-test.png)

**Więcej do wybierania i dużych projektów** (menu Obiekt):
- **Linie do wybierania**: cięcia przez odpad między kształtami (w
  poprzek, pionowe albo oba), co tyle mm, do ramki.
- **Podziel na pasy**: projekt szerszy niż ploter (albo dłuższy niż
  arkusz) w zachodzących na siebie pasach, ułożonych jeden za drugim na
  materiale.

<a id="s9"></a>

## 9. Rysowanie pisakiem

Włóż pisak do oprawki (czubek tuż nad papierem) i przełącz narzędzie w
lewym panelu na **Pisak**. Nie ma wtedy przesunięcia noża ani nadcięcia;
ustaw **grubość pisaka** i to, gdzie leży kreska: **na linii**, **na
zewnątrz linii** albo **wewnątrz linii**. Użyj małego nacisku.

**Wypełnienie** (Shift+F, tylko pisak) wypełnia zamknięte kształty wzorem:
linie, kratka, fale, zygzak, okręgi, plaster miodu, romby, cegiełki albo
koncentryczne, z odstępem, kątem i marginesem. Dla pełnego zamalowania
ustaw odstęp trochę mniejszy niż grubość pisaka.

![Wypełnienie]({{ img }}fill.png)

<a id="s10"></a>

## 10. Kolory

Projekt może mieć kilka kolorów: pisakiem każdy kolor rysuje się swoim
pisakiem, nożem każdy kolor tnie się z folii w tym kolorze. Ploter ma jedną
oprawkę, więc Vintyl robi jeden kolor, zatrzymuje się i prosi o następny
pisak (albo następną folię).

**Otwieranie SVG w kilku kolorach.** Okno pokazuje każdy kolor z pliku i
kolor projektu, do którego trafi. Podobne kolory (dwa różowe, dwa szare,
których oko prawie nie odróżnia) są **łączone** w jeden, więc rysuje je
jeden pisak; **Każdy osobno** zostawia każdy kolor oddzielnie, a
**Wszystko w jednym kolorze** otwiera rysunek jak dawniej, w jednym
kolorze. Każdy wiersz możesz zmienić przed kliknięciem **Otwórz**. Kształty
wypełnione w pliku dostają wypełnienie liniami dla pisaka. Żeby
wypróbować, otwórz demo:
[vintyl-demo.svg](https://github.com/cyryllo/vintyl/raw/main/docs/demo/vintyl-demo.svg).

![Kolory pliku SVG przy otwieraniu: dziewięć kolorów pliku trafia do pięciu kolorów projektu]({{ img }}colours-open.png)

**Panel Kolory** (w lewym panelu, gdy projekt ma więcej niż jeden kolor)
pokazuje kolory **w kolejności rysowania**: strzałki przesuwają wybrany
kolor wcześniej albo później (zwykle najpierw jasne kolory, a czarny kontur
na końcu). Odznaczony kolor zostaje pominięty w zadaniu. Kliknięcie koloru
zaznacza jego elementy; zębatka ustawia jego nazwę, kolor oraz własną
**grubość pisaka** i to, **gdzie leży kreska** (puste: jak w oknie). Na
arkuszu i na liście elementów każdy element jest w swoim kolorze.

Żeby dać elementom inny kolor, użyj prawego przycisku myszy → **Kolor**:
wybierz jeden z kolorów projektu albo **Nowy kolor…**.

![Projekt w pięciu kolorach, rysowany pisakami]({{ img }}colours.png)

**Start kolor po kolorze.** Lista kontrolna wymienia kolory w ich
kolejności. Przed każdym kolorem okno prosi o włożenie jego pisaka (albo
założenie jego folii) i o to, żeby nie ruszać materiału: punkt zerowy
zostaje ten sam, więc kolory trafiają dokładnie jeden na drugi. **Pomiń ten
kolor** przechodzi do następnego; **Zakończ** kończy w tym miejscu.

![Przed drugim kolorem: włóż różowy pisak]({{ img }}colour-pause.png)

<a id="s11"></a>

## 11. Ustawienia

Ustawienia (Ctrl+,):
- **Rysowanie**: odstęp siatki, przyciąganie do innych kształtów oraz co
  okno kolorów proponuje najpierw dla SVG w kilku kolorach: **Łącz
  podobne** albo **Każdy osobno**.
- **Język i wygląd**: polski, angielski, niemiecki, hiszpański, francuski
  albo portugalski brazylijski (albo jak w systemie), wygląd
  jasny, ciemny albo jak w systemie; zmieniają się przy następnym
  uruchomieniu.
- **Aktualizacje**: sprawdzaj raz dziennie, czy jest nowa wersja (pytany
  jest tylko GitHub, nic o Tobie nie jest wysyłane), albo **Sprawdź
  teraz**. Nowa wersja pokaże się w pasku pod wstążką.

<a id="s12"></a>

## 12. Skróty klawiszowe

Pomoc → Skróty klawiszowe (Ctrl+F1) pokazuje wszystkie klawisze, z
wyszukiwaniem.

![Skróty klawiszowe]({{ img }}shortcuts.png)

| Klawisz | Polecenie | Klawisz | Polecenie |
|---|---|---|---|
| V | Zaznacz | Ctrl+N / O / S | Nowy / Otwórz / Zapisz |
| N | Węzły | Ctrl+E | Zapisz .hpgl |
| R / E / P | Prostokąt / Elipsa / Wielokąt | Ctrl+Z / Ctrl+Shift+Z | Cofnij / Ponów |
| L / Shift+L | Linia łamana / Linia | Ctrl+C / X / V | Kopiuj / Wytnij / Wklej |
| B / F | Pióro / Odręcznie | Ctrl+D / Del | Duplikuj / Usuń |
| T | Tekst | Ctrl+A | Zaznacz wszystko |
| O | Odsunięcie | Ctrl+G / Ctrl+Shift+G | Grupuj / Rozgrupuj |
| Shift+T | Wzór z kształtów | Ctrl+[ / Ctrl+] | Obróć w lewo / w prawo |
| Shift+F | Wypełnienie (pisak) | Ctrl+M / Ctrl+Shift+M | Lustro / Odwróć |
| M | Miarka | Ctrl+Home | Do 0,0 |
| Ctrl+0 | Dopasuj | Ctrl+K | Ścieżka noża |
| + / - | Przybliż / Oddal | Ctrl+' | Siatka |

<a id="s13"></a>

## 13. Gdy coś nie działa

- **„Brak uprawnień do…” albo „Nie ma teraz…” pod ploterem**: dołącz do grupy
  (zobacz [1](#s1)) i zaloguj się ponownie; sprawdź kabel, czy ploter jest
  włączony i jego port w ustawieniach plotera (Szukaj).
- **Tnie za głęboko albo nie przecina**: zmień nacisk na panelu plotera,
  wytnij test noża i wpisz wartość w materiale.
- **Narożniki są zaokrąglone**: przesunięcie noża jest za małe; **na
  narożnikach wystają małe chorągiewki**: jest za duże. Ustaw je dla swojego
  ostrza (zobacz [Ostrza i przesunięcie noża](#ostrza): 0,25 mm dla ostrza
  45°, 0,50 mm dla większości ostrzy 60°) i wytnij test noża jeszcze raz.
- **„Projekt nie mieści się na folii”**: wystaje przed punkt zerowy
  albo poza szerokość cięcia; użyj Do 0,0 albo przesuń go.
- **Błąd albo informacja, czy Twój ploter działa**: Pomoc → Raport
  diagnostyczny pokazuje wersje, wyniki kontroli i dziennik (bez nazwy
  użytkownika i bez projektów); **Zgłoś problem** albo **Zgłoś mój ploter**
  otwiera formularz na GitHubie z raportem już skopiowanym. W tej wersji
  mogą się jeszcze trafić drobne błędy w interfejsie: dziękujemy za każde
  zgłoszenie.
