# Do zrobienia

Lista roboczych zadań Vintyla. Zrobione rzeczy przechodzą do
[CHANGELOG.md](CHANGELOG.md).

## Paczki

- [ ] **Flathub.** Flatpak jest gotowy (od 0.9.3, plik w wydaniach:
  `packaging/flatpak/io.github.cyryllo.Vintyl.yml`). Żeby był w sklepie
  Flathub: wniosek (pull request) do github.com/flathub/flathub z tym
  manifestem; robi go właściciel (konto, przegląd Flathuba). Uprawnienie
  `--device=all` (port plotera) trzeba tam uzasadnić.

- [ ] **Wspólne repozytorium APT dla wszystkich programów** (`cyryllo/apt`,
  adres `https://cyryllo.github.io/apt`): Vintyl, LamaDeck, Kerfly, millwise
  i kolejne, instalowane i aktualizowane zwykłym `apt`. Na wzór repozytorium
  LamaDecka (`apt-repo.sh`, gałąź `gh-pages`, klucz RSA 4096, 3 ostatnie
  wersje w puli):
  1. repozytorium `cyryllo/apt` tylko ze skryptem, automatem i listą
     projektów (`projects.txt`), bez plików `.deb` w historii gita;
  2. automat (GitHub Actions): pobiera `.deb` z ostatnich wydań każdego
     projektu (`gh release download`), buduje spisy dla `amd64`, `all` i
     `arm64`, podpisuje `Release`/`InRelease` kluczem z sekretów, publikuje
     na Pages z artefaktu;
  3. uruchamiany sygnałem `repository_dispatch` z wydania każdego projektu
     (token w sekretach projektów), do tego raz dziennie i ręcznie;
  4. każda paczka dokłada wspólny wpis `/etc/apt/sources.list.d/cyryllo.sources`
     i klucz, więc jedna instalacja daje aktualizacje wszystkich programów;
  5. LamaDeck: kolejna wersja w starym repozytorium podmienia użytkownikom
     wpis i klucz na wspólne;
  6. Kerfly i millwise najpierw potrzebują własnej paczki `.deb` (na wzór
     `packaging/linux/build-deb.sh` Vintyla).
  Limit Pages ok. 1 GB (Vintyl 46 MB na wersję). Założenie repozytorium,
  klucza i tokenów na GitHubie: tylko na polecenie właściciela.

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
