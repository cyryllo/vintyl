# Etap B: plan (SZKIC, jeszcze nie do akceptacji)

To szkic przygotowany przed testami z ploterem. Miejsca oznaczone
**[po A4]** uzupełnię po poniedziałku i dopiero wtedy dam Ci plan do
akceptacji. Kodu programu (etap C) nie zaczynam bez niej.

---

## 1. Co budujemy

**Vintyl**: program do ploterów tnących, głównie na Linuksa (inne systemy
później). Składa się z trzech części:

1. **Rdzeń `vintyl`:** pakiet Pythona **bez Qt**. Zamienia ścieżki na
   polecenia plotera i wysyła je do pliku albo na port. Można go testować
   bez okienek.
2. **Wiersz poleceń:** `vintyl cut projekt.svg --profil sk-870t` (domyślnie
   na sucho, czyli do pliku `.hpgl`).
3. **Wpięcie w Kerfly:** Kerfly woła rdzeń z tego samego okna, w którym
   rysujesz.

**Pytanie do Ciebie:** czy Vintyl ma być też **osobnym programem
z okienkiem** (stąd ikona), czy wystarczy rdzeń, wiersz poleceń i okno
w Kerfly? Plan poniżej zakłada to drugie. Osobne okno można dołożyć
później na tym samym rdzeniu.

---

## 2. Struktura pakietu rdzenia

```
vintyl/                      repo github.com/cyryllo/vintyl
  pyproject.toml             zależności: pyserial; svgelements tylko dla wiersza poleceń
  src/vintyl/
    geometry.py              linie łamane w mm: długości, kierunki, łuki, punkt w wielokącie
    order.py                 kolejność cięcia: najpierw kształty wewnętrzne, krótkie przejazdy
    knife.py                 nadcięcie, kompensacja noża, podnoszenie na ostrych kątach
    profile.py               profil urządzenia: odczyt, zapis, sprawdzanie wartości
    profiles/sk-870t.toml    profile dostarczane z programem
    protocols.py             HPGL, DMPL: zamiana ruchów na tekst dla plotera
    safety.py                kontrola przed wysłaniem: pole robocze, ujemne współrzędne
    transport.py             wyjście: plik albo port szeregowy (porcje, przepływ, czekanie, stop)
    job.py                   cała droga: ścieżki -> osie -> kolejność -> nadcięcie -> nóż -> polecenia
    cli.py                   wiersz poleceń
  tests/                     testy automatyczne (pytest)
  tools/                     narzędzia pomocnicze (ikony, wzorce Inkcuta, kroki A4)
  assets/                    ikona, logo
```

**Wejście rdzenia:** lista linii łamanych w **milimetrach**, oś Y w górę,
zero w lewym dolnym rogu materiału. Krzywe zamienia na odcinki ten, kto
woła rdzeń, czyli Kerfly albo wiersz poleceń. Rdzeń nie zna formatów
plików.

**Punkt wpięcia w Kerfly:** mały plik w Kerfly (np.
`kerfly/core/plotter.py`), który:
1. bierze warstwę „cięcie” przez `layers.compile_layer(...)`;
2. zamienia wiersze `[x, y, pętla]` w calach na linie łamane w mm;
3. woła `vintyl.job`.

W oknie Kerfly dochodzi menu „Ploter”: wybór profilu, podgląd ścieżki
noża, zapis do pliku, wysyłka, Stop. Kod lasera się nie zmienia. Vintyl
jest dla Kerfly zależnością opcjonalną: bez niego menu jest wyszarzone.

---

## 3. Format profilu urządzenia

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

Drugi profil (mniejszy ploter) powstanie po odczycie tabliczki.

---

## 4. Skąd bierzemy kod (licencje)

| Fragment | Źródło | Licencja, autorzy | Jak |
|---|---|---|---|
| Kompensacja noża, nadcięcie, łuki | CutScape `filters.py`, `geometry.py` (pomysł z Inkcuta) | GPL-3.0; jetpax, Jairus Martin i autorzy Inkcuta | **piszemy sami na podstawie pomysłu**, z podziękowaniem w nagłówku (patrz niżej) |
| Kolejność „najpierw wewnętrzne” | Kerfly `pathopt.py` albo CutScape `order()` | GPL-3.0-or-later (Scorch, Kerfly) / GPL-3.0 | wersja z Kerfly: ta sama licencja co Kerfly |
| HPGL, DMPL (z poprawioną skalą trybu 1) | CutScape `protocols.py` | GPL-3.0 | kilka linii; piszemy sami, sprawdzamy na wzorcach |
| Podnoszenie noża na ostrych kątach | RedsailCut `sharp_corners.py` | MIT, Anders Lorentzen | przeniesienie z nagłówkiem MIT |
| Kontrola przed wysłaniem, czekanie wg czasu ruchu, DTR/RTS po otwarciu | RedsailCut `hpgl.py`, `serial_io.py` | MIT, Anders Lorentzen | przeniesienie fragmentów z nagłówkiem MIT |
| Wysyłka porcjami, czekanie na opróżnienie bufora | CutScape `transports.py` | GPL-3.0 | pomysł; piszemy sami |
| Inkcut, cuthulhu, KM Plot | — | — | tylko do porównania, nic nie kopiujemy |

**Licencja Vintyl, do decyzji:** proponuję **GPL-3.0-or-later**, tak jak
Kerfly.
- Pliki CutScape i Inkcuta mają „GPL v3” bez „or later”. Gdybyśmy
  skopiowali z nich kod, Vintyl byłby w praktyce na samej GPL-3.0.
- Dlatego te kilkadziesiąt linii (kompensacja, nadcięcie, protokoły)
  proponuję napisać samemu na podstawie opisanego pomysłu. Pomysł nie
  podlega prawu autorskiemu. Źródło inspiracji i tak podamy w nagłówku.
- Kod z MIT (RedsailCut) i GPL-3.0-or-later (Kerfly) można przenosić
  wprost.

---

## 5. Testy automatyczne

1. **Jednostki:** 20 mm = 800 jednostek HPGL. Cale z Kerfly z osią Y w górę
   zamieniają się poprawnie na mm.
2. **HPGL:** kwadrat daje dokładnie oczekiwany tekst. Zawsze jest `PU`
   przed powrotem do zera i na końcu. Brak ujemnych współrzędnych.
3. **DMPL:** tryb 1 (1000 jednostek na cal) i tryb 3 dają oczekiwany tekst.
4. **Porównanie z Inkcutem:** nasze wyjście zgadza się ze wzorcami
   z `tests/wzorce_inkcut/` po uwzględnieniu skali 1021/1016 i marginesu
   2,8 mm.
5. **Nadcięcie:** tylko kształty zamknięte, dalej po obwodzie o zadaną
   długość. Otwarte linie bez zmian.
6. **Kompensacja noża:** offset 0 nie zmienia ścieżki (tryb pisaka).
   Kwadrat ma wysunięte narożniki z łukami. Nadcięcie nie ginie (błąd
   Inkcuta). Powrót do zera bez przesunięcia.
7. **Kolejność:** dziura przed obrysem, a litera „O” wnętrzem przed
   zewnętrzem.
8. **Pole robocze:** za szeroki projekt jest odrzucany z podaniem, o ile mm
   wystaje. Projekt dokładnie na krawędzi przechodzi.
9. **Osie:** zamiana i odwrócenie osi zostawiają projekt przy zerze.
10. **Profil:** zapis i odczyt dają to samo. Brakujące pola dostają wartości
    domyślne, a złe wartości są odrzucane z czytelnym komunikatem.
11. **Wysyłka** (port testowy `loop://`, bez plotera):
    - trafiają dokładnie te bajty, w porcjach;
    - czekanie wynika z prędkości;
    - Stop dosyła `PU;`;
    - zablokowany port przy RTS/CTS daje błąd po czasie, a nie zawieszenie;
    - tryb na sucho w ogóle nie otwiera portu.
12. **Wiersz poleceń:** SVG zamienia się na plik `.hpgl`.
13. **Brak Qt:** rdzeń nie importuje Qt (jak test w Kerfly).
14. **(w Kerfly)** wiersze `[x, y, pętla]` z warstwy cięcia zamieniają się
    na linie łamane w mm.

---

## 6. Kolejność prac (etap C)

1. Generator HPGL z zapisem do pliku i testami 1–4, 8–10, 12–13.
2. Wysyłka na port (test 11), potem próba na ploterze z pisakiem.
3. Kompensacja noża, nadcięcie, kolejność (testy 5–7), potem próba z nożem
   na folii.
4. Wpięcie w Kerfly: menu, podgląd ścieżki noża, Stop (test 14).

---

## 7. Świadomie odkładamy

- kopie, odbicie lustrzane (poza ustawieniem osi), ramka do obierania;
- cięcie po nadruku: ploter nie ma czujnika znaczników;
- DMPL poza trybami 1 i 3, inne języki (GP-GL, CAMM);
- Windows i macOS;
- osobny program z okienkiem (jeśli zdecydujesz, że ma być);
- `vpype`: niepotrzebny, kolejność ścieżek mamy własną.

---

## 8. Otwarte punkty do uzupełnienia po A4

- skala: 40 czy 40,2 jednostki na mm;
- język: HPGL czy DMPL (i który tryb);
- kierunek osi i położenie punktu zerowego;
- kontrola przepływu i prędkość portu;
- czy ploter reaguje na `VS` i `FS`, czy odpowiada na `OH;` i `OI;`;
- układ USB (CH340 czy FTDI) i nazwa portu;
- model mniejszego plotera.
