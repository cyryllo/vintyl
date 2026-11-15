# Etap B: plan (SZKIC, jeszcze nie do akceptacji)

To szkic przygotowany przed testami z ploterem. Miejsca oznaczone
**[po A4]** uzupełnię po poniedziałku i dopiero wtedy dam Ci plan do
akceptacji. Kodu programu (etap C) nie zaczynam bez niej.

**Już ustalone (14.11.2026):**
- nazwa **Vintyl**, ikona B (nóż i pasek folii w kształcie V);
- licencja **GPL-3.0-or-later**, tak jak Kerfly;
- Vintyl ma **własne okno**. Rysowanie będzie podobne do Kerfly, ale lewy
  panel ma mniej opcji niż w laserze;
- głównie Linux, inne systemy w późniejszych etapach;
- Vintyl obsługuje **tylko plotery tnące do folii**. Kerfly zostaje
  wyłącznie dla laserów i nie będzie wysyłać na ploter. Z Kerfly tylko
  **kopiujemy kod rysowania**; wspólnej biblioteki nie robimy.

---

## 1. Co budujemy

Vintyl to program do ploterów tnących. Składa się z dwóch części
w jednym repo:

1. **Rdzeń `vintyl.core`:** pakiet **bez Qt**. Zamienia ścieżki na
   polecenia plotera i wysyła je do pliku albo na port. Można go testować
   bez okienek i używać z wiersza poleceń
   (`vintyl cut projekt.svg --profil sk-870t`, domyślnie na sucho do pliku).
2. **Okno `vintyl.gui`:** PySide6, jak w Kerfly. Rysowanie, wczytywanie
   SVG i DXF, podgląd ścieżki noża, wysyłka i Stop. Okno tylko woła rdzeń.

Kerfly nie korzysta z Vintyl ani odwrotnie. Z Kerfly bierzemy tylko kopię
kodu rysowania.

Zasada ta sama co w Kerfly: nic w `vintyl/core/` nie importuje Qt, a test
to pilnuje.

---

## 2. Okno Vintyl

Układ jak w Kerfly: wstążka na górze, pasek opcji kształtu, narzędzia
rysowania po prawej, obszar roboczy na środku, panel zadania po lewej.

**Obszar roboczy:**
- zamiast stołu lasera jest **pas folii**: szerokość cięcia z profilu
  (SK-870T: 780 mm), a długość bez limitu, bo to rolka;
- widać punkt zerowy (Origin z panelu plotera) i kierunek podawania folii.

**Narzędzia rysowania (prawy pasek), jak w Kerfly:**
- zaznaczanie i edycja węzłów;
- prostokąt, elipsa, wielokąt, linia, linia łamana, krzywa;
- tekst, także tekst na ścieżce.

Bez narzędzi typowo laserowych: rastra, wypełnienia liniami, wzorów,
zawiasów.

**Lewy panel: mniej niż w laserze.** Propozycja do przejrzenia:
- **Projekt:** lista elementów z ptaszkiem „tnij” i kolejnością (jak w
  Kerfly) oraz rozmiar całości w mm.
- **Ploter:**
  - wybór profilu (Seiki SK-870T, VEVOR KI-375A);
  - port i stan połączenia;
  - przesunięcie noża i nadcięcie, w trybie pisaka bez kompensacji;
  - opcjonalnie prędkość i nacisk; puste pole = ustawienie z panelu
    plotera.
- **Na dole:**
  - „Zapisz .hpgl”;
  - Start, Stop (wysyłka przerwana, nóż w górę);
  - ptaszek „na sucho”, domyślnie włączony;
  - szacowany czas cięcia.

Bez warstw z mocą, przejściami i kerfem, bez materiałów lasera, bez
przejazdu głowicy po obrysie lasera.

**[po A4]** jakie funkcje dokładnie zostają, ustalimy na podstawie tego,
co umie Twój ploter (np. czy reaguje na prędkość i nacisk z komputera).

---

## 3. Struktura repo

```
vintyl/                      github.com/cyryllo/vintyl
  pyproject.toml             rdzeń: pyserial; okno: PySide6-Essentials, svgelements
  src/vintyl/
    core/
      geometry.py            linie łamane w mm: długości, kierunki, łuki, punkt w wielokącie
      order.py               kolejność cięcia: najpierw kształty wewnętrzne, krótkie przejazdy
      knife.py               nadcięcie, kompensacja noża, podnoszenie na ostrych kątach
      profile.py             profil urządzenia: odczyt, zapis, sprawdzanie wartości
      profiles/sk-870t.toml  profile dostarczane z programem
      protocols.py           HPGL, DMPL: zamiana ruchów na tekst dla plotera
      safety.py              kontrola przed wysłaniem: pole robocze, ujemne współrzędne
      transport.py           plik albo port szeregowy (porcje, przepływ, czekanie, Stop)
      job.py                 cała droga: ścieżki -> osie -> kolejność -> nadcięcie -> nóż -> polecenia
      shapes.py, curves.py   kształty i krzywe (przeniesione z Kerfly, w mm)
      loaders.py             SVG i DXF przez svgelements i czytnik DXF z Kerfly
      cli.py                 wiersz poleceń
    gui/                     okno PySide6 (rysowanie przeniesione z Kerfly)
  tests/                     testy automatyczne (pytest)
  tools/                     ikony, wzorce Inkcuta, kroki A4
  assets/                    ikona, logo
```

**Jednostki w całym Vintyl: milimetry.** Rdzeń Kerfly liczy w calach,
z osią Y w górę, bo tak było w K40 Whisperer. Przy przenoszeniu kodu
z Kerfly zamieniamy to na mm od razu.

---

## 4. Co bierzemy z Kerfly do okna

Ta sama licencja (GPL-3.0-or-later) i ten sam autor, więc można przenosić
wprost, z nagłówkami „Kerfly contributors” i źródłem.

| Z Kerfly | Do czego | Uwagi |
|---|---|---|
| `kerfly/gui/preview.py` | obszar roboczy, zaznaczanie, uchwyty | stół lasera zamieniamy na pas folii |
| `kerfly/gui/node_editor.py`, `core/curves.py`, `core/snap.py` | edycja węzłów i krzywych, przyciąganie | już w mm |
| `kerfly/core/shapes.py`, `gui/text_shapes.py`, `gui/tool_options.py` | kształty, tekst, pasek opcji | bez operacji raster, wypełnienie, wzory, zawiasy |
| `kerfly/core/layout.py`, `core/pathopt.py` | elementy na pasie, kolejność cięcia | z cali na mm |
| `kerfly/gui/icons`, `i18n` | ikony, tłumaczenia | — |
| okno główne | **nie kopiujemy w całości** | `main_window.py` ma 4680 linii, głównie laser; piszemy nowe, mniejsze, z kawałków |

**Ustalone:** kopiujemy kod z Kerfly, bez wspólnej biblioteki. Kerfly
zostaje bez zmian. Pamiętamy, że poprawki w rysowaniu trzeba przenosić
ręcznie, jeśli mają trafić do obu programów.

---

## 5. Format profilu urządzenia

Plik TOML, czytelny i z komentarzami. Odczyt przez `tomllib` z biblioteki
standardowej, zapis przez prosty własny zapis płaskich pól.

```toml
name = "Seiki SK-870T"

# pole robocze
width_mm = 780            # szerokość cięcia      [po A4: sprawdzić 780 vs 860]
length_mm = 0             # 0 = bez limitu (rolka)

# połączenie
port = "/dev/ttyUSB0"
baud = 9600               # jak w menu plotera    [po A4]
flow = "none"             # none / rtscts / xonxoff [po A4]

# język
language = "hpgl"         # hpgl / dmpl           [po A4]
dmpl_mode = 3             # tylko dla dmpl
units_per_mm = 40.0       # [po A4: 40 czy 40,2 jak w Inkcucie]

# osie: jak obrócić projekt, żeby wyszedł na ploterze tak jak na ekranie
swap_xy = false           # [po A4]
invert_x = false
invert_y = false

# nóż
knife_offset_mm = 0.0     # 0 = pisak (bez kompensacji); ostrze 45°: 0,20–0,30
overcut_mm = 0.5          # nadcięcie kształtów zamkniętych
corner_deg = 5.0          # mniejsze zakręty traktujemy jak prostą linię
lift_below_deg = 0.0      # 0 = wyłączone; np. 30: nóż podnosi się na ostrych kątach

# prędkość i nacisk: puste = jak na panelu plotera
speed_cm_s = ""           # VS              [po A4: czy ploter reaguje]
force_g = ""              # FS              [po A4, krok 10]

# wysyłka
chunk_bytes = 64
pacing = "time"           # none / time (czekanie wg szacowanego czasu ruchu)
lookahead_s = 0.3         # ile ruchu ploter może mieć naprzód (krótko = szybki Stop)
```

Drugi profil: **VEVOR KI-375A** (ok. 285 mm szerokości cięcia według
sprzedawcy). Na obu ploterach tniesz tym samym sterownikiem, więc
najpewniej różnią się tylko polem roboczym. [po A4]

---

## 6. Skąd bierzemy kod rdzenia (licencje)

| Fragment | Źródło | Licencja, autorzy | Jak |
|---|---|---|---|
| Kompensacja noża, nadcięcie, łuki | pomysł z Inkcuta i CutScape (`filters.py`, `geometry.py`) | GPL-3.0 (bez „or later”); Jairus Martin i autorzy Inkcuta, jetpax | **piszemy sami na podstawie pomysłu**, z podziękowaniem w nagłówku |
| HPGL, DMPL (z poprawioną skalą trybu 1) | CutScape `protocols.py` | jw. | kilka linii, piszemy sami, sprawdzamy na wzorcach |
| Wysyłka porcjami, czekanie na opróżnienie bufora | CutScape `transports.py` | jw. | pomysł, piszemy sami |
| Kolejność „najpierw wewnętrzne” | Kerfly `core/pathopt.py` | GPL-3.0-or-later; Scorch, Kerfly contributors | przeniesienie z nagłówkiem |
| Podnoszenie noża na ostrych kątach | RedsailCut `sharp_corners.py` | MIT, Anders Lorentzen | przeniesienie z nagłówkiem MIT |
| Kontrola przed wysłaniem, czekanie wg czasu ruchu, DTR/RTS po otwarciu | RedsailCut `hpgl.py`, `serial_io.py` | MIT, Anders Lorentzen | przeniesienie fragmentów z nagłówkiem MIT |
| Inkcut, cuthulhu, KM Plot | — | — | tylko do porównania, nic nie kopiujemy |

Dlaczego piszemy sami zamiast kopiować z CutScape i Inkcuta: ich pliki
mają „GPL v3” bez „or later”. Skopiowany kod zamknąłby Vintyl na samej
GPL-3.0, a ustaliliśmy GPL-3.0-or-later.

---

## 7. Testy automatyczne

**Rdzeń:**
1. **Jednostki:** 20 mm = 800 jednostek HPGL.
2. **HPGL:** kwadrat daje dokładnie oczekiwany tekst. Zawsze jest `PU`
   przed powrotem do zera i na końcu. Brak ujemnych współrzędnych.
3. **DMPL:** tryb 1 (1000 jednostek na cal) i tryb 3 dają oczekiwany tekst.
4. **Porównanie z Inkcutem:** zgodność ze wzorcami z
   `tests/wzorce_inkcut/` po uwzględnieniu skali 1021/1016 i marginesu
   2,8 mm.
5. **Nadcięcie:** tylko kształty zamknięte, dalej po obwodzie. Otwarte
   linie bez zmian.
6. **Kompensacja noża:** offset 0 nie zmienia ścieżki. Kwadrat ma wysunięte
   narożniki z łukami. Nadcięcie nie ginie (błąd Inkcuta). Powrót do zera
   bez przesunięcia.
7. **Kolejność:** dziura przed obrysem, a litera „O” wnętrzem przed
   zewnętrzem.
8. **Pole robocze:** za szeroki projekt jest odrzucany z podaniem, o ile mm
   wystaje. Projekt dokładnie na krawędzi przechodzi.
9. **Osie:** zamiana i odwrócenie osi zostawiają projekt przy zerze.
10. **Profil:** zapis i odczyt dają to samo. Brakujące pola dostają
    wartości domyślne, a złe wartości są odrzucane z czytelnym komunikatem.
11. **Wysyłka** (port testowy `loop://`):
    - trafiają dokładnie te bajty, w porcjach;
    - czekanie wynika z prędkości;
    - Stop dosyła `PU;`;
    - zablokowany port przy RTS/CTS daje błąd po czasie, a nie zawieszenie;
    - tryb na sucho w ogóle nie otwiera portu.
12. **Wiersz poleceń:** SVG zamienia się na plik `.hpgl`.
13. **Brak Qt w rdzeniu.**
14. **Wczytywanie:** SVG i DXF dają te same wymiary w mm co w Kerfly.

**Okno** (jak w Kerfly, `QT_QPA_PLATFORM=offscreen`):

15. Narysowany kształt trafia do zadania z właściwym rozmiarem
    i położeniem.
16. Element z odznaczonym „tnij” nie trafia do zadania.
17. Podgląd ścieżki noża pokazuje to samo, co pójdzie do pliku.
18. Stop w trakcie wysyłki (na porcie testowym) kończy wysyłkę i dosyła
    `PU;`.
19. Projekt poza pasem folii blokuje Start z komunikatem.

---

## 8. Kolejność prac (etap C)

1. Generator HPGL z zapisem do pliku i testami (1–4, 8–10, 12–13).
2. Wysyłka na port (test 11), potem próba na ploterze z pisakiem.
3. Kompensacja noża, nadcięcie, kolejność (testy 5–7), potem próba z nożem
   na folii.
4. Okno: najpierw wczytanie SVG, podgląd ścieżki noża, zapis i wysyłka,
   Stop. Potem rysowanie przeniesione z Kerfly (testy 14–19).

---

## 9. Świadomie odkładamy

- kopie, odbicie lustrzane (poza ustawieniem osi), ramka do obierania;
- cięcie po nadruku: ploter nie ma czujnika znaczników;
- DMPL poza trybami 1 i 3, inne języki (GP-GL, CAMM);
- Windows i macOS;
- `vpype`: niepotrzebny, kolejność ścieżek mamy własną.

---

## 10. Otwarte punkty do uzupełnienia po A4

- skala: 40 czy 40,2 jednostki na mm;
- język: HPGL czy DMPL (i który tryb);
- kierunek osi i położenie punktu zerowego;
- kontrola przepływu i prędkość portu;
- czy ploter reaguje na `VS` i `FS`, czy odpowiada na `OH;` i `OI;`;
- układ USB (CH340 czy FTDI) i nazwa portu;
- napis z tabliczki KI-375A i jego szerokość cięcia.
