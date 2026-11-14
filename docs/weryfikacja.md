# Etap A: weryfikacja (stan na 14.11.2026)

Plik opisuje, co sprawdziłem przed pisaniem kodu, jak to zrobiłem i czy wynik
zgadza się z opisem projektu (sekcje 3–5). Kroki A1–A3 są zrobione, A5 bez
plotera też. Krok A4 (sprzęt) i A5 na ploterze czekają do poniedziałku
16.11: lista kroków jest w [poniedzialek-A4.md](poniedzialek-A4.md).

Oznaczenia: **[POTW]** sprawdzone w źródle, **[POSR]** wniosek albo dane
z pokrewnego sprzętu, **[BRAK]** nie dało się ustalić.

---

## Rozbieżności z opisem projektu (najważniejsze na górze)

1. **Inkcut liczy HPGL w innej skali niż 40 jednostek na mm.**
   Inkcut mnoży współrzędne przez `1021/90` (1021 jednostek na cal, czyli
   około 40,2 na mm). CutScape, RedsailCut i cuthulhu używają 40 na mm
   (1016 na cal). Różnica wynosi 0,49%, czyli około 3,8 mm na długości 780 mm.
   Skutek: w kroku A5 zapis z Inkcuta **nie będzie** miał tych samych liczb
   co nasz generator, choć oba programy wytną ten sam kształt. Z ploterem
   trzeba sprawdzić linijką, która skala daje dokładnie 20 mm. [POTW, kod:
   `inkcut/device/protocols/hpgl.py`, `inkcut/core/svg.py`]

2. **Profil „SeikiTech SK-870T” w Inkcucie nie zawiera ustawień portu.**
   Ustawia tylko szerokość 86 cm, języki HPGL i DMPL oraz połączenie
   szeregowe. 9600 bodów i RTS/CTS z wpisu na forum to ustawienia autora
   wpisu, nie profilu. Domyślnie Inkcut ma 9600 bodów i wyłączoną kontrolę
   przepływu. [POTW, `inkcut/device/drivers/manifest.enaml`,
   `transports/serialport/plugin.py`]

3. **CutScape opisuje VEVOR KH-870 inaczej niż wpis na forum.**
   Profil „VEVOR KH-870”: język **DMPL (tryb 3)**, szerokość 780 mm, osie
   zamienione (oś X idzie wzdłuż podawania folii). Przy bliźniaczym KH-720
   jest uwaga, że HPGL działa na tym oprogramowaniu plotera zawodnie
   (źródło: zgłoszenie inkcut#428). Wpis na forum mówi: Vevor 870, HPGL.
   Nie wiadomo, czy KH-870 to ten sam ploter co SK-870T. Wniosek: w A4
   trzeba sprawdzić **oba** języki i kierunek osi. [POTW dla treści profilu,
   POSR dla tożsamości maszyn]

4. **PySide6-Essentials nie zawiera QtSerialPort.**
   W wersji 6.12.0 (zainstalowanej w Kerfly) nie ma takiego modułu,
   a `from PySide6 import QtSerialPort` kończy się błędem. Moduł jest
   w osobnym pakiecie PySide6-Addons (6.12.0 na PyPI), ale tego nie
   instalowałem. Rdzeń i tak ma być bez Qt, więc zostaje pyserial. [POTW]

5. **RedsailCut nie „czeka po każdym ruchu” na ploter.**
   Ploter niczego mu nie potwierdza. Program liczy, ile czasu zajmie ruch
   przy ustawionej prędkości, i tyle odczekuje, z zapasem 0,15 s. Do tego
   opis na górze `serial_io.py` mówi, że domyślnie jest RTS/CTS, a kod
   domyślnie używa trybu bez kontroli przepływu. [POTW, kod]

6. **Ploter ma 4 MB pamięci, więc „stop” z komputera nie zatrzyma go od
   razu.** Wszystkie trzy programy wzorcowe przy przerwaniu dosyłają `PU;`
   albo `IN;` na koniec kolejki. Ploter wykona je dopiero po tym, co ma już
   w pamięci. Dlatego wysyłka „z czekaniem”, w której ploter dostaje
   niewiele naprzód, to jedyny sposób, żeby przycisk Stop działał szybko.
   Do sprawdzenia w A4. [POSR, wniosek z instrukcji i kodu]

7. **Drobne różnice w wersjach i opisach:**
   - Inkcut: na PyPI jest 2.1.8 (zgodnie z opisem), ale w repo jest już
     2.2.0, jeszcze niewydana. Inkcut nie przypina wersji Qt (komentarz:
     „Let users install whatever Qt they want”), więc „Qt5” z opisu jest
     nieaktualne. [POTW]
   - CutScape: wersja 0.6.3, nie 0.6. [POTW]
   - RedsailCut: sam rdzeń (HPGL, kompensacja, port) nie jest związany
     z macOS. „Tylko macOS” dotyczy okienek, pakowania i komunikatów
     o uprawnieniach. [POTW]
   - KM Plot: serwer `git.knoxmakers.org` nie działa (brak wpisu DNS),
     a na GitHubie nie ma kopii. Licencji nie sprawdziłem, więc nic z tego
     projektu nie bierzemy. [BRAK]

8. **Uwaga o licencjach przy przenoszeniu kodu.** Kerfly ma licencję
   GPL-3.0-or-later. Inkcut i CutScape mają w plikach zapis „GPL v3” bez
   „or later”. Kod z nich da się włączyć do Kerfly, ale moduł plotera
   z takim kodem będzie w praktyce na GPL-3.0. RedsailCut (MIT) nie ma tego
   ograniczenia. Do decyzji w etapie B. [POTW dla plików licencji, POSR dla
   interpretacji]

9. **Inkcut przy włączonej kompensacji noża pomija nadcięcie** i przesuwa
   końcowy powrót do zera. Szczegóły w A5. [POTW, wynik uruchomienia]

---

## A1. Kerfly (czytane z kopii z GitHuba w `~/ref-plotery/Kerfly`)

| Co | Jak sprawdzone | Wynik | Zgodne z sekcją 3? |
|---|---|---|---|
| Licencja | `LICENSE`, nagłówki plików | GPL-3.0-or-later | tak |
| Wersja, liczba commitów | `kerfly/__init__.py`, `git rev-list --count HEAD` | 1.5.0, dokładnie 200 commitów, ostatni 07e58e0 z 14.11.2026 | tak (z POSR na POTW) |
| Zależności | `requirements.txt` | lxml, pyusb, pillow, PySide6-Essentials, svgelements, segno, bez wersji; opcjonalnie pyclipper; dla deweloperów babel | tak |
| Python | `python3 --version` | 3.13.5 (system i środowisko Kerfly) | — |
| Zainstalowane wersje (środowisko Kerfly) | `pip list` | lxml 6.1.3, pyusb 1.3.1, pillow 13.0.0, PySide6-Essentials 6.12.0, svgelements 1.9.6, segno 1.6.6, pyclipper 1.4.0 | — |
| Rdzeń bez Qt | `DEVELOPMENT.md`, test „core runs without any GUI toolkit loaded” | `kerfly/core/` nie importuje Qt | — |

### Mapa plików

- `kerfly/core/`: rdzeń bez okienek.
  - `loaders.py`: wczytywanie SVG, DXF, G-code i grafik.
  - `design.py`: jeden wczytany projekt.
  - `layout.py`: elementy na stole (położenie, skala, obrót).
  - `layers.py`: warstwy i składanie zadania.
  - `pathopt.py`: kolejność cięcia, najpierw kształty wewnętrzne.
  - `curves.py`: krzywe Béziera i ich zamiana na odcinki.
  - `shapes.py`, `generators.py`: rysowane kształty i gotowe wzory.
  - `offset.py`: odsuwanie konturów (pyclipper).
  - `job.py`: zamiana na dane lasera (format EGV).
  - `laser.py`: obsługa płyty lasera.
  - `config.py`, `settings.py`: ustawienia.
- `kerfly/gui/`: okno PySide6. Najważniejsze pliki to `main_window.py`
  (4680 linii) i `worker.py` (wątki wysyłki).
- W katalogu głównym leżą stare pliki K40 Whisperera: `egv.py`,
  `nano_library.py` (USB lasera), `ecoords.py`, `svg_reader.py`, `dxf.py`
  i inne.

### Jak przechowywane są ścieżki

- Obiekt `Design` ma cztery części: `raster`, `vector_engrave` (niebieskie),
  `vector_cut` (czerwone) i `gcode`. Każda to `ECoord`.
- `ECoord.ecoords` to lista wierszy `[x, y, numer_pętli]`. Jest to już
  **linia łamana**: krzywe są zamienione na odcinki z dokładnością 0,02 mm
  (`curves.FLATNESS_MM`).
- **Jednostka: cale.** Oś Y idzie w górę, zero jest w lewym górnym rogu
  stołu, a stół zajmuje y od −wysokości do 0 (`layout.py`).
- Rysowane kształty trzymają też krzywe Béziera (`curves.py`), ale
  w milimetrach i z osią Y w dół. Do lasera i tak idą jako odcinki.
- Dobry punkt wpięcia: `layers.compile_layer(elements, warstwa, warstwy)`
  zwraca `Design` jednej warstwy we wspólnym układzie stołu i jej położenie.
  Z tego mamy gotowe pętle `[x, y, pętla]`. Jest też gotowa kolejność
  „najpierw wewnętrzne” (`pathopt.optimize_paths`, autor Scorch, GPL).

### Warstwa urządzenia i czy da się dołożyć ploter

- `LaserController` w `kerfly/core/laser.py` to konkretna klasa pod płytę
  K40: USB przez `nano_library`, dane w formacie EGV, moc, przejazd do
  pozycji domowej. **Nie ma wspólnego interfejsu „urządzenia”.**
- Okno woła `self.laser` bezpośrednio w około 25 miejscach `main_window.py`
  (połącz, zwolnij, pozycja domowa, start zadania i inne). Wątki w
  `worker.py` też wywołują `laser.send` wprost. `PauseControl` jest wspólny,
  ale opisany pod pakiety USB.
- **Wniosek:** rdzeń plotera da się dołożyć obok bez zmian w kodzie lasera.
  Bierze z Kerfly tylko pętle `[x, y, pętla]`, a resztę robi sam. W oknie
  potrzebne będzie osobne menu lub panel „Ploter” i osobny wątek wysyłki,
  wzorowany na `worker.py`, ale bez wspólnej klasy z laserem. Pojęcia
  typowo laserowe (raster, moc, kolor czerwony = cięcie, niebieski =
  grawer) trzeba będzie przełożyć na ploter: np. tnie się warstwa „cut”,
  a reszta jest pomijana. [POSR, do ustalenia w etapie B]

### Testy

- `tests/test_core.py` (bez okienek), `tests/test_gui.py`
  (`QT_QPA_PLATFORM=offscreen`), `test_i18n.py`, `test_stamp.py`,
  `regression.py` (przez xvfb; porównuje bajty z wersją wyjściową),
  `test_references.py`, `test_release.py`, `test_random.py`. Opis jest
  w `DEVELOPMENT.md`.
- Na początku pracy, zanim ustaliliśmy, że lokalnego repo nie ruszam,
  uruchomiłem raz `tests/test_core.py` w lokalnym repo: wszystkie przypadki
  przeszły. Od tej pory w Kerfly niczego nie uruchamiam. Testy modułu
  plotera będą w `vintyl-cut`.

---

## A2. Projekty wzorcowe (sklonowane do `~/ref-plotery`, tylko czytane)

| Projekt | Licencja (plik) | Ostatni commit | Opis z sekcji 6 a kod |
|---|---|---|---|
| Inkcut | GPL-3.0 (`LICENSE`); nagłówki „GPL v3”, autor Jairus Martin (frmdstryr) | 30.10.2026 | PyPI 2.1.8 z 22.06.2026: **tak**. „Qt5”: **nie**, Qt nieprzypięte. Profil SK-870T: patrz rozbieżność 2 |
| CutScape | GPL-3.0 (`LICENSE`); historia od Inkcuta, autor rozszerzenia jetpax | 13.11.2026 | fork Inkcuta bez Qt: **tak**. Prototyp nietestowany na ploterze: **tak** (README). Wersja 0.6.3 |
| RedsailCut | MIT, Anders Lorentzen 2026 | 28.04.2026 (v0.2.0) | MIT, PyQt6, sprawdzony na RS720C: **tak**. „Tylko macOS”: dotyczy okienek |
| cuthulhu | GPL-3.0-or-later (README, nagłówki SPDX) | 12.11.2026 | Rust, moduł `driver-hpgl`: **tak** (napisany pod GCC Puma IV) |
| KM Plot | [BRAK] serwer niedostępny | [BRAK] | [BRAK], nic nie bierzemy |

### Inkcut: co gdzie jest

- **Profil SK-870T:** `inkcut/device/drivers/manifest.enaml`, linia 228:
  szerokość 86 cm, języki `hpgl` i `dmpl`, połączenie `serial`. Nic więcej.
- **HPGL** (`device/protocols/hpgl.py`):
  - na starcie `IN;`, potem `PU x,y;` i `PD x,y;`;
  - opcja „oddzielne PU/PD i PA”;
  - `VS` i `FS` są wysyłane tylko wtedy, gdy włączysz je w ustawieniach;
  - na końcu znów `IN;`;
  - skala 1021 jednostek na cal (rozbieżność 1).
- **DMPL** (`device/protocols/dmpl.py`):
  - tryby 1, 2, 3, 4 i 6; tryb 1 zaczyna się od `;:HAEC1`, tryb 3 od ` ;:H A L0 `;
  - ruchy `U x,y` i `D x,y`, prędkość `V n`, nacisk `BP n`, narzędzie `EC n`.
  - Uwaga: tryb 1 ustawia jednostkę 0,001 cala (`EC1`), a Inkcut nadal
    liczy w skali 1021 na cal. CutScape to poprawił (1000 na cal dla
    trybu 1). [POTW, kod]
- **Kompensacja noża:** `device/filters/blade_offset.py` (opis w porównaniu
  niżej). Wymaga Qt (`QPainterPath`).
- **Nadcięcie:** `device/filters/overcut.py`. Kształt zamknięty jest cięty
  dalej po własnym obwodzie o zadaną długość.
- **Dzielenie na porcje** (`device/plugin.py`, `submit`): Inkcut nie dzieli
  danych na bajty.
  - Wysyła po jednym poleceniu i czeka, aż system je wypchnie.
  - Potem odczekuje tyle, ile ploter potrzebuje na ten odcinek przy
    ustawionej prędkości.
  - Opcja „interpolate” tnie ścieżki na kawałki co 1 mm, żeby dało się
    wstrzymać w połowie linii.
  - Pauza: przestaje wysyłać. Anulowanie: przerywa pętlę i wysyła końcowe
    `IN;`.

### CutScape: czy logika jest oddzielona od interfejsu

**Tak.** Moduł Inkscape (`inkex`) importują tylko `document.py`, `preview.py`
i `marks.py`. Te pliki korzystają wyłącznie ze standardowej biblioteki
Pythona i nadają się do przeniesienia:

- `geometry.py`: odległości, kierunki, łuki, punkt w wielokącie;
- `filters.py`: kolejność „najpierw wewnętrzne”, powtórzenia, nadcięcie,
  ramka do obierania, kompensacja noża;
- `protocols.py`: HPGL, DMPL (z poprawioną skalą trybu 1), GP-GL, CAMM, G-code;
- `devices.py`: profile, w tym SK-870T i VEVOR KH-870;
- `transports.py`, część `to_serial`: pyserial, kontrola przepływu do
  wyboru, wysyłka po 256 bajtów, czekanie na opróżnienie bufora;
- `job.py`: składanie całości.

Zastrzeżenia: brak przerwania pracy w trakcie (całe zadanie idzie do bufora
systemu), brak czekania dostosowanego do prędkości plotera, nietestowane
na ploterze.

### RedsailCut: co gdzie jest

- **Kompensacja noża:** `src/redsailcut/blade_offset.py`, domyślnie wyłączona
  (tryb pisaka).
- **Nadcięcie:** w tym samym pliku. Przedłuża ostatni odcinek prosto,
  a nie wzdłuż obwodu.
- **Ostre narożniki:** `sharp_corners.py`. Przy kącie ostrzejszym niż 30°
  nóż się podnosi, obraca i wchodzi ponownie.
- **Czekanie przy wysyłce:** `serial_io.py`, `send_hpgl`. Wysyła wiersz po
  wierszu i czeka, ile ploter potrzebuje na ruch, z zapasem 0,15 s.
  Minimum to 15 ms, a po podniesieniu noża 120 ms (rozbieżność 5).
- **Przerwanie:** dosyła `PU;PU0,0;SP0;`.
- **Tryb na sucho:** zapis pliku `.plt`, domyślnie włączony.
- **Bezpieczeństwo przed wysłaniem:** `validate_hpgl_safety` odrzuca ujemne
  współrzędne i podejrzanie długie odcinki cięcia. Warto mieć to samo.
- **Ustawienia wyjściowe:** port otwierany z DTR i RTS w stanie wysokim
  i 300 ms przerwy. Na RS720C bez tego ploter nie reagował.
- **Zapytania diagnostyczne:** `probe_cutter` wysyła `OI;`, `OS;`, `OE;`
  i `OA;` z limitem 2 s.
- Wartości startowe z README (offset 0,20–0,30 mm dla ostrza 45°, nadcięcie
  0,5 mm): **zgodne z opisem**. [POTW]

### cuthulhu: dla porównania (kodu nie przenosimy)

- HPGL: `IN;`, potem `PU x,y;` i `PD x,y;`, 1016 jednostek na cal.
- Prędkości i nacisku nie wysyła wcale, bo ustawia się je na panelu plotera.
- Przerwanie: samo `PU;`, „na ile się da”.
- Port: 8N1, bez kontroli przepływu, limit 5 s.
- Rozdziela profil maszyny, sterownik i transport, podobnie jak chcemy
  zrobić w Pythonie.

### Kompensacja noża: porównanie

Nóż wleczony ma czubek kawałek za osią obrotu. Bez poprawki narożniki
wychodzą zaokrąglone, a zamknięte kształty nie domykają się.

- **Inkcut:** każdy punkt drogi przesuwa do przodu o wartość offsetu,
  w kierunku ruchu. Na zakręcie ostrzejszym niż 5° oś robi mały łuk wokół
  czubka noża, żeby nóż obrócił się w miejscu. Działa też bezpośrednio na
  krzywych. Jest jednak zrośnięta z Qt, więc do rdzenia bez Qt trzeba by ją
  przepisać.
- **CutScape:** ten sam pomysł co w Inkcucie (przesunięcie do przodu i łuk
  na zakrętach powyżej 5°), przepisany na zwykłe linie łamane
  w milimetrach, bez Qt. Pamięta kierunek noża między kształtami.
  Kilkadziesiąt linii czystego Pythona, licencja GPL-3.0.
- **RedsailCut:** prostszy. Tylko na wyraźnym narożniku przedłuża odcinek
  o offset, bez łuku, a następny odcinek zaczyna z tego wysuniętego punktu.
  Na ostrych kątach (poniżej 30°) podnosi nóż i zaczyna od nowa. Mniej
  dokładny w narożnikach, ale bardzo przewidywalny, a sprawdzony na
  prawdziwym ploterze. Licencja MIT.

**Propozycja:** jako podstawę wziąć wersję z CutScape: ten sam sprawdzony
pomysł co w Inkcucie, ale bez Qt i na liniach łamanych, czyli na tym, co
daje Kerfly. Jako opcję dodać z RedsailCut podnoszenie noża na ostrych
kątach i sprawdzanie bezpieczeństwa przed wysłaniem. Nadcięcie robić „po
obwodzie”, jak w Inkcucie i CutScape, bo na okręgach jest dokładniejsze.

Porównanie zrobiłem z czytania kodu. Próba przepuszczenia kwadratu przez
funkcje CutScape i RedsailCut została zablokowana przez zabezpieczenie
(uruchamianie pobranego kodu), więc **liczb z uruchomienia nie mam**.
Sprawdzimy to testami we własnym kodzie w etapie C.

---

## A3. Biblioteki (PyPI, 14.11.2026)

| Pakiet | Wersja z opisu | Stan na PyPI | Zgodne? | Uwagi |
|---|---|---|---|---|
| pyserial | 3.5 (2020, do Pythona 3.8) | 3.5, 23.11.2020, klasyfikatory do 3.8 | tak | **Działa na Pythonie 3.13.5**: instalacja w osobnym środowisku, port testowy `loop://` z RTS/CTS zapisuje i czyta. Na komputerze są teraz tylko `/dev/ttyS0–3`, bez `ttyUSB` (ploter niepodłączony) |
| svgelements | 1.9.6 (2023) | 1.9.6, 17.08.2023 | tak | ta sama wersja jest w Kerfly |
| vpype | 1.15.0 (08.2025, Python 3.11–3.13) | 1.15.0, 04.08.2025, `>=3.11,<3.14` | tak | na razie niepotrzebny: Kerfly ma własną kolejność ścieżek |
| inkcut | 2.1.8 (22.06.2026) | 2.1.8, wysłany 22.06.2026 (tag v2.1.8 z 21.06) | tak | w repo jest już 2.2.0 |
| PySide6-Essentials | — | 6.12.0 | — | **brak QtSerialPort** (sprawdzone) |
| PySide6-Addons | — | 6.12.0 | — | QtSerialPort ma być tutaj; nie instalowałem, więc [POSR]. Rdzeń i tak bez Qt, więc pyserial |

---

## A4. Sprzęt: czeka na Twoje „tak” przy każdym kroku

Na dziś niczego nie uruchamiałem. Nawet `groups` (krok 2) czeka na Twoją zgodę.

| Krok | Stan |
|---|---|
| 1. `lsusb` i `dmesg` przed podłączeniem i po nim | czeka |
| 2. `groups` (dialout) | czeka |
| 3. Prędkość portu z panelu | czeka na Twój odczyt |
| 4. Tabliczki obu ploterów | czeka na Twój odczyt |
| 5–10. Ruch plotera (pisak, papier) | czeka. Dokładna treść każdego kroku jest w [poniedzialek-A4.md](poniedzialek-A4.md), w tym DMPL tryb 3 i sprawdzenie kierunku osi (rozbieżność 3) |

## A5. Test odniesienia z Inkcutem (część bez plotera: zrobiona)

**Jak:** Inkcut 2.1.8 z PyPI zainstalowany w osobnym środowisku
`~/ref-plotery/venv-inkcut` razem z PyQt6. Pominąłem `pycups` (drukarki),
bo wymaga systemowego `libcups2-dev`, a do tego testu nie jest potrzebny.
Skrypt [tools/inkcut_wzorzec.py](../tools/inkcut_wzorzec.py) odtwarza
`Device.submit()` z 2.1.8 krok po kroku, na własnych funkcjach Inkcuta
(init, process, protokół, filtry), z buforem testowym zamiast portu.
Profil: SeikiTech SK-870T (86 cm). Kwadrat 20×20 mm. Wyniki są
w [tests/wzorce_inkcut/](../tests/wzorce_inkcut/).

| Plik | Co Inkcut wysłałby |
|---|---|
| `hpgl_podstawowy.hpgl` | `IN;PU113,917;PD917,917;PD917,113;PD113,113;PD113,917;PU0,0;IN;` |
| `hpgl_vs20_fs80.hpgl` | `IN;FS80; VS20;` + jak wyżej |
| `hpgl_nadciecie0.5.hpgl` | jak podstawowy + `PD133,917;` (0,5 mm dalej po obwodzie) |
| `hpgl_noz0.25_nadciecie0.5.hpgl` | `IN;PU123,917;PD927,917;PD917,907;PD917,103;PD907,113;PD103,113;PD113,123;PD113,927;PU0,10;IN;` |
| `dmpl_tryb1.dmpl` | `;:HAEC1 U113,917  D917,917 … U0,0 ` |
| `dmpl_tryb3.dmpl` | ` ;:H A L0  U113,917  D917,917 … U0,0 ` |

**Co z tego wynika:**

1. **Bok kwadratu ma 804 jednostki zamiast 800.** To skutek skali 1021 na
   cal (rozbieżność 1). Przy 40 jednostkach na mm wyjdzie 20,1 mm. Ploter
   rozstrzygnie, która skala jest właściwa.
2. **Początek nie jest w 0, tylko w 113.** Inkcut zostawia margines 10 px
   przy 90 DPI, czyli 2,8 mm (`material.padding`, domyślnie). [POTW, kod]
3. **Brak `SP1;`.** Inkcut nie wybiera narzędzia. `FS` jest wysyłane przed
   `VS`, ze spacją po średniku (`FS80; `). Wartość `VS` to po prostu liczba
   cm/s z ustawień.
4. **Kompensacja noża w Inkcucie gubi nadcięcie.** Po przesunięciu punktów
   kształt przestaje być „zamknięty” (koniec nie trafia w początek), a filtr
   nadcięcia działa tylko na kształtach zamkniętych. Przy włączonych obu
   opcjach nadcięcia **nie ma** w wyniku. Do tego końcowy powrót do zera
   też został przesunięty (`PU0,10;`). U nas: najpierw nadcięcie, potem
   kompensacja, a powrót do zera bez kompensacji. [POTW, wynik uruchomienia]
5. **Narożniki z kompensacją:** przy 0,25 mm łuk wokół narożnika to jeden
   krótki odcinek (np. `PD927,917;PD917,907;`). Przy tak małym promieniu
   to wystarcza.
6. **DMPL tryb 1:** `EC1` ustawia jednostkę 0,001 cala, a Inkcut liczy
   w skali 1021 na cal. Kwadrat wyszedłby 804/1000 cala, czyli 20,4 mm
   (o 2% za duży). CutScape to poprawia. Tryb 3 nie ustawia jednostki, więc
   zostaje domyślna jednostka plotera: [BRAK], do sprawdzenia w A4.

**Wersje Inkcuta:** wcześniej w A2 czytałem gałąź master (2.2.0). Pliki
protokołów i portu w 2.1.8 różnią się od niej, ale wnioski z A2 są aktualne
także dla 2.1.8: ta sama skala, ten sam profil SK-870T, te same ustawienia
domyślne portu (9600 bodów, bez kontroli przepływu). Kod kompensacji noża
i wysyłki (`plugin.py`) jest w 2.1.8 taki sam jak w master. Wersja 2.1.8
działa na Twisted, master na asyncio.

**Czeka na ploter:** wycięcie tego kwadratu przez Inkcuta na prawdziwym
porcie i pomiar linijką (krok A4.6–A4.7).
