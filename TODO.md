# Do zrobienia

Lista roboczych zadań Vintyla. Zrobione rzeczy przechodzą do
[CHANGELOG.md](CHANGELOG.md).

## Funkcje



## Paczki

- [ ] **Pakiet .deb** (Debian, Ubuntu, Mint) obok AppImage.
- [ ] **Flatpak** (Flathub); dostęp do /dev/usb/lp* i portów szeregowych
  trzeba sprawdzić, bo Flatpak domyślnie ich nie daje.

## Później

- [ ] **Dopracowanie kolorów (0.9).** Uwagi po testach właściciela, gdy
  będzie na nie czas.

## Wersja 1.x

- [ ] **Plotery rysujące na GRBL / FluidNC** (wiele domowych ploterów z
  pisakiem: USB-serial, G-code). Pisak podnosi się na trzy sposoby, każdy
  do ustawienia w profilu plotera:
  1. **serwo**: w GRBL zwykle przez wyjście PWM wrzeciona, `M3 S…` /
     `M5` (forki grbl-servo, Grbl_Pen_Servo; tryb lasera `$32=0`, bo
     inaczej pisak nie podnosi się między kreskami); w FluidNC wyjście
     `rc_servo` sterowane osią Z;
  2. **silnik krokowy na osi Z**: `G0 Z…` w górę, `G1 Z… F…` w dół;
  3. **elektromagnes wł./wył.**: `M3` / `M5` (albo `M7` / `M8`).
  Do zrobienia: język G-code w profilu z wyborem sposobu (polecenia
  „podnieś” i „opuść” do wpisania, krótkie `G4 P…` po każdej zmianie, bo
  serwo potrzebuje chwili), prędkość w mm/min (`F`), wysyłanie z
  czekaniem na `ok` (bufor odbioru GRBL ok. 128 bajtów, liczenie znaków),
  Stop przez `!` (wstrzymanie) i Ctrl-X (reset), stan przez `?`, bazowanie
  `$H` tam, gdzie są krańcówki. Źródła: gnea/grbl
  `doc/markdown/interface.md` (protokół), dokumentacja FluidNC (sprawdzić
  klucze `rc_servo` / `solenoid`), vankesteren/grbl-servo,
  bdring/Grbl_Pen_Servo. Bez takiej maszyny: testy z udawanym GRBL.

## Na koniec

- [ ] **Wersja 1.0**, kiedy właściciel uzna, że program jest gotowy.
