# Kroki A4: lista na poniedziałek 16.11.2026

**Jutro testujemy mniejszy ploter: VEVOR KI-375A** (potwierdziłeś
15.11; wcześniej zapisany jako „SK420” i „KI-275A”). Według opisu
sprzedawcy: 375 mm podawania, ok. 285 mm szerokości cięcia, nacisk do
500 g [POSR]. Dokładny napis z tabliczki i tak zapiszemy (krok 4).

Na obu ploterach tniesz tym samym sterownikiem (SignMaster), więc
najpewniej mówią tym samym językiem i mają te same ustawienia portu.
To, co ustalimy jutro, sprawdzimy potem na SK-870T jednym kwadratem.
[POSR: do potwierdzenia]

Inkcut ma gotowy profil tylko dla SK-870T, ale to nie znaczy, że na pewno
działa. Na forum ktoś potwierdził na nim tylko ruchy, nie cięcie folii.
Dla KI-375A Inkcut ani CutScape nie mają profilu. Kwadrat 20 mm
z odstępem 10 mm mieści się na obu ploterach.

Każdy krok robię dopiero po Twoim „tak”. Przy krokach z ruchem: **pisak
zamiast noża i papier**.

**Jak zatrzymać ploter (kroki 5–10):**
- **Test**: wstrzymuje pracę, a ponowne naciśnięcie ją wznawia;
- **Leave**: przełącza ploter w tryb offline, w którym ignoruje dane;
- **wyłącznik zasilania**: zawsze działa.

Ploter ma 4 MB pamięci. To, co już do niego doszło, wykona nawet po
przerwaniu wysyłki na komputerze, dlatego do natychmiastowego zatrzymania
służy klawisz **Test**, a nie Ctrl+C.

Narzędzie do wysyłania: [tools/a4_port.py](../tools/a4_port.py). Bez
`--wyslij` tylko pokazuje treść. **Przeczytaj je przed poniedziałkiem.**
Fragmenty krytyczne, czyli otwarcie portu, wysyłka i przerwanie, mają
komentarze. Pliki testowe są w [tests/a4/](../tests/a4/).

---

## Bez ruchu plotera

### 1. USB: identyfikator, układ, nazwa portu
- Przed podłączeniem: `lsusb` oraz `sudo dmesg | tail -n 30`. Na tym
  komputerze `dmesg` wymaga uprawnień administratora (`dmesg_restrict=1`),
  więc to polecenie wpisujesz Ty albo ja przez `journalctl -k -n 30`, jeśli
  jesteś w grupie `adm`.
- Po podłączeniu i włączeniu plotera: to samo jeszcze raz.
- Zapisuję: identyfikator USB (np. `1a86:7523` = CH340, `0403:6001` = FTDI),
  nazwę układu i nazwę portu (`/dev/ttyUSB0` albo `/dev/ttyACM0`).

### 2. Grupa dialout
- `groups`. Jeśli nie ma `dialout`: `sudo usermod -aG dialout $USER`,
  potem wylogowanie i ponowne zalogowanie (to robisz Ty).

### 3. Prędkość portu z panelu
- Odczytujesz z menu plotera ustawioną prędkość (np. 9600 / 38400).

### 4. Tabliczki
- Dokładny napis z tabliczki SK-870T i mniejszego plotera
  („SK420”, może SK-375T).

---

## Z ruchem (pisak, papier)

We wszystkich plikach 40 jednostek = 1 mm. Kwadrat 20×20 mm zaczyna się
10 mm od punktu zerowego. Nad kwadratem jest kreska 10 mm wzdłuż osi X:
po niej poznamy, w którą stronę idzie X.

### 5. Otwarcie portu i samo `IN;`
- **Ploter ma:** nic nie robić (`IN;` tylko zeruje jego ustawienia).
- **Polecenie:**
  `.venv/bin/python tools/a4_port.py --port /dev/ttyUSB0 --bod <z kroku 3> --tekst "IN;" --wyslij`
- Sprawdzamy: czy port się otwiera i czy nie ma błędu uprawnień.

### 6. Kwadrat 20×20 mm w HPGL, bez kontroli przepływu
- **Treść** ([tests/a4/kwadrat_20mm.hpgl](../tests/a4/kwadrat_20mm.hpgl)):
  `IN;SP1;PU400,400;PD1200,400;PD1200,1200;PD400,1200;PD400,400;PU400,400;PU400,1400;PD800,1400;PU800,1400;PU0,0;`
- **Ploter ma:**
  1. podnieść pisak i dojechać 10 mm od zera;
  2. narysować kwadrat;
  3. podnieść pisak;
  4. narysować kreskę 10 mm nad kwadratem, wzdłuż osi X;
  5. wrócić do zera z podniesionym pisakiem.
- Mierzymy linijką bok kwadratu i kreskę. Zapisujemy, gdzie jest punkt
  zerowy i kierunki osi X i Y.
- **Jeśli HPGL nie zadziała** (ploter stoi albo rysuje bzdury): ten sam
  kształt w DMPL tryb 3
  ([tests/a4/kwadrat_20mm_dmpl3.dmpl](../tests/a4/kwadrat_20mm_dmpl3.dmpl)),
  bo tak opisuje VEVOR KH-870 profil w CutScape. Jednostka DMPL na tym
  ploterze jest nieznana: przy 0,1 mm kwadrat wyjdzie 80 mm, więc połóż
  większy arkusz.

### 7. Ten sam kwadrat z RTS/CTS
- To samo co w kroku 6, z `--przeplyw rtscts`.
- Zapisujemy różnice. Jeśli kabel albo adapter nie przenosi linii CTS,
  narzędzie po 10 s zgłosi, że ploter nie przyjmuje danych. To też jest
  wynik.

### 8. Zapytanie `OH;` (rozmiar pola)
- **Ploter ma:** nic nie robić, tylko odpowiedzieć.
- `--tekst "OH;" --czytaj 2 --wyslij`
- Zapisujemy odpowiedź albo jej brak. Opcjonalnie to samo z `OI;`
  (identyfikacja modelu), jak w RedsailCut.

### 9. Prędkość: `VS10` i `VS40`
- Pliki [tests/a4/kwadrat_vs10.hpgl](../tests/a4/kwadrat_vs10.hpgl) i
  [tests/a4/kwadrat_vs40.hpgl](../tests/a4/kwadrat_vs40.hpgl). Ten sam kwadrat,
  jeden po drugim (w pliku ze `VS40` 40 cm/s = 400 mm/s).
- Oceniasz wzrokiem, czy drugi był szybszy. Przy okazji: czy prędkość na
  panelu się zmieniła.

### 10. Nacisk `FS` i nóż na folii
- **Tylko jeśli się zgodzisz**, osobno, po krokach 1–9.

---

## A5 na prawdziwym ploterze

- Inkcut (`~/ref-plotery/venv-inkcut`) z profilem SeikiTech SK-870T tnie
  ten sam kwadrat. Wzorzec tego, co wyśle, już mamy
  ([tests/wzorce_inkcut/](../tests/wzorce_inkcut/)).
- Mierzymy linijką: bok z Inkcuta (skala 1021/cal) i nasz (40/mm). Ten
  pomiar rozstrzygnie, która skala jest właściwa.
