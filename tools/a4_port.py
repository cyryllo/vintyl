#!/usr/bin/env python3
"""
Narzędzie do kroków A4 (weryfikacja plotera). To nie jest część programu
Vintyl, tylko „śrubokręt” do testów: wysyła na port dokładnie podany tekst
i opcjonalnie czeka na odpowiedź plotera.

Bezpieczeństwo:
- bez --wyslij tylko POKAZUJE, co by wysłał (domyślnie nic nie idzie na port);
- nie dokłada żadnych poleceń od siebie: co podasz, to pójdzie;
- przerwanie Ctrl+C w trakcie wysyłki dosyła „PU;” (podnieś nóż/pisak).

Przykłady:
    .venv/bin/python tools/a4_port.py --port /dev/ttyUSB0 --tekst "IN;"
    .venv/bin/python tools/a4_port.py --port /dev/ttyUSB0 --plik tests/a4/kwadrat_20mm.hpgl --wyslij
    .venv/bin/python tools/a4_port.py --port /dev/ttyUSB0 --tekst "OH;" --czytaj 2 --wyslij
"""
import argparse
import sys
import time


def parse_args(argv):
    p = argparse.ArgumentParser(description="Wysyła tekst na port plotera (kroki A4).")
    p.add_argument("--port", required=True, help="np. /dev/ttyUSB0")
    p.add_argument("--bod", type=int, default=9600, help="prędkość portu, jak w menu plotera")
    p.add_argument("--przeplyw", choices=["brak", "rtscts", "xonxoff"], default="brak",
                   help="kontrola przepływu (domyślnie brak)")
    zrodlo = p.add_mutually_exclusive_group(required=True)
    zrodlo.add_argument("--tekst", help="polecenia do wysłania, np. 'IN;'")
    zrodlo.add_argument("--plik", help="plik z poleceniami (.hpgl / .dmpl)")
    p.add_argument("--czytaj", type=float, default=0.0,
                   help="po wysłaniu czekaj tyle sekund na odpowiedź plotera (np. 2)")
    p.add_argument("--porcja", type=int, default=64,
                   help="ile bajtów naraz (małe porcje = Ctrl+C działa szybciej)")
    p.add_argument("--wyslij", action="store_true",
                   help="naprawdę wyślij; bez tego tylko pokazuje treść")
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    if a.plik:
        with open(a.plik, "rb") as f:
            data = f.read()
    else:
        data = a.tekst.encode("ascii")

    # Najpierw zawsze pokazujemy dokładnie to, co pójdzie na port.
    print("Port: %s, %d bodów, 8 bitów, bez parzystości, 1 bit stopu, przepływ: %s"
          % (a.port, a.bod, a.przeplyw))
    print("Do wysłania (%d bajtów):" % len(data))
    print("  " + data.decode("ascii", "replace"))
    if not a.wyslij:
        print("Tryb pokazowy: nic nie wysłano (dodaj --wyslij).")
        return 0

    import serial   # pyserial; importujemy dopiero tu, żeby tryb pokazowy działał bez niego

    # OTWARCIE PORTU
    # CO: 8N1 (8 bitów, bez parzystości, 1 bit stopu), prędkość i przepływ z opcji.
    # DLACZEGO write_timeout: przy RTS/CTS, gdy ploter (albo kabel) nie daje
    # sygnału „gotów”, zapis by wisiał w nieskończoność. Po 10 s zgłaszamy błąd.
    s = serial.Serial(a.port, a.bod, bytesize=8, parity="N", stopbits=1,
                      rtscts=(a.przeplyw == "rtscts"), xonxoff=(a.przeplyw == "xonxoff"),
                      timeout=0.2, write_timeout=10)
    try:
        s.reset_input_buffer()
        start = time.monotonic()
        wyslane = 0
        try:
            # WYSYŁKA PORCJAMI
            # DLACZEGO: po każdej porcji czekamy, aż system wypchnie ją z bufora
            # (flush). Wtedy Ctrl+C przerywa szybko, a nie po całym pliku.
            # Ploter ma własną pamięć (4 MB), więc to, co już do niego doszło,
            # i tak wykona: do natychmiastowego zatrzymania służy klawisz Test.
            for i in range(0, len(data), a.porcja):
                s.write(data[i:i + a.porcja])
                s.flush()
                wyslane = min(len(data), i + a.porcja)
        except KeyboardInterrupt:
            # PRZERWANIE: podnieś nóż/pisak. Ploter wykona to po tym, co już ma w pamięci.
            print("\nPrzerwano po %d z %d bajtów, wysyłam PU;" % (wyslane, len(data)))
            s.write(b"PU;")
            s.flush()
            return 1
        except serial.SerialTimeoutException:
            print("Ploter nie przyjmuje danych od 10 s (przepływ: %s). "
                  "Czy jest online (nie Leave) i czy kabel ma linie RTS/CTS?" % a.przeplyw)
            return 2
        print("Wysłano %d bajtów w %.2f s." % (wyslane, time.monotonic() - start))

        # ODCZYT ODPOWIEDZI (np. na OH;): czytamy wszystko, co przyjdzie w zadanym czasie.
        if a.czytaj > 0:
            koniec = time.monotonic() + a.czytaj
            odp = b""
            while time.monotonic() < koniec:
                odp += s.read(256)
            if odp:
                print("Odpowiedź (%d bajtów): %r" % (len(odp), odp))
            else:
                print("Brak odpowiedzi w %.1f s." % a.czytaj)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
