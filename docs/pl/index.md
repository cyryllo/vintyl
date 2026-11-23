---
layout: default
lang: pl
other_lang: index.html
title: Vintyl po polsku
wide: true
description: Vintyl to darmowy program do ploterów tnących folię na Linuksa. Rysuj, otwieraj pliki SVG i DXF, układaj je i tnij na ploterach VEVOR, Seiki i podobnych.
---
{% assign img = '/screenshots/pl/' | relative_url %}

<div class="hero">
  <img src="{{ '/assets/logo.svg' | relative_url }}" alt="Logo Vintyla">
  <div>
    <h1>Vintyl</h1>
    <p>Darmowy program do ploterów tnących folię, na Linuksa. Rysujesz, układasz i tniesz w jednym oknie.</p>
    <p class="badges"><span>Linux</span><span>AppImage</span><span>Wolne oprogramowanie</span><span>6 języków</span></p>
  </div>
</div>

<div class="buttons">
  <a class="button primary" href="#pobierz">Pobierz</a>
  <a class="button" href="{{ '/pl/guide.html' | relative_url }}">Instrukcja</a>
  <a class="button" href="{{ '/pl/guide.html#s1' | relative_url }}">Instalacja</a>
</div>

<div class="shot"><a href="{{ img }}main-window.png"><img src="{{ img }}main-window.png" alt="Okno Vintyla: koło, gwiazda, napis i serce z wzorem gwiazdek na arkuszu plotera 780 mm"></a></div>

<p class="lead">Vintyl obsługuje popularne, niedrogie <strong>plotery z nożem wleczonym</strong> (VEVOR, Seiki i wiele modeli na tej samej płycie sterującej), do których producent daje program tylko na Windowsa, np. SignMaster. Rysujesz albo otwierasz plik, widzisz go na arkuszu tak, jak materiał leży w ploterze, sprawdzasz nacisk i prędkość i tniesz prosto z okna.</p>

> **Wersja 0.9.2, do użytku.** Przetestowana i czysto tnie na
> **VEVOR KI-375A** i **Seiki SK-870T**. W interfejsie mogą się jeszcze
> trafić drobne błędy: prosimy,
> [zgłaszaj je]({{ site.repo }}/issues/new/choose).

<div class="stats">
  <div><strong>4</strong><span>gotowe profile ploterów</span></div>
  <div><strong>7</strong><span>materiałów dla noża i pisaka</span></div>
  <div><strong>8</strong><span>gotowych kształtów i kody QR</span></div>
  <div><strong>9</strong><span>wzorów wypełnienia dla pisaka</span></div>
  <div><strong>0,0</strong><span>projekt do punktu zerowego jednym klawiszem</span></div>
</div>

## Co potrafi Vintyl

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}knife-path.png"><img loading="lazy" src="{{ img }}knife-path.png" alt="Ścieżka noża na arkuszu z kolejnością cięć"></a></div>
  <div class="text-col">
    <h3>Czyste cięcie nożem wleczonym</h3>
    <ul>
      <li>Kompensacja noża na narożnikach (gładkie łuki zostają gładkie) i nadcięcie, więc każdy zamknięty kształt się domyka.</li>
      <li>Najpierw kształty wewnętrzne: nic nie odpada, zanim nie zostaną wycięte jego otwory.</li>
      <li>Ramka do wybierania dookoła projektu i linie do wybierania przez odpad.</li>
      <li>Ścieżka noża na arkuszu, z kolejnością cięć i przejazdami.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col small"><a href="{{ img }}check-list.png"><img loading="lazy" src="{{ img }}check-list.png" alt="Lista kontrolna przed Startem: nacisk i prędkość do ustawienia na panelu plotera"></a></div>
  <div class="text-col">
    <h3>Materiały i sprawdzenie przed każdym cięciem</h3>
    <ul>
      <li>Folia winylowa, flex, folia odblaskowa, papier i karton oraz Twoje własne materiały, każdy z naciskiem i prędkością dla każdego plotera.</li>
      <li>Przed Startem krótka lista kontrolna pokazuje dużymi cyframi, co ustawić na panelu plotera, i co sprawdzić.</li>
      <li>Test noża (kwadrat z trójkątem), żeby dobrać nacisk dla nowego materiału.</li>
      <li>Nic nie trafia do plotera, dopóki nie potwierdzisz.</li>
    </ul>
  </div>
</div>

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}pattern-of-shapes.png"><img loading="lazy" src="{{ img }}pattern-of-shapes.png" alt="Wzór z serduszek wstawiany w prostokąt, z podglądem"></a></div>
  <div class="text-col">
    <h3>Rysowanie i edycja</h3>
    <ul>
      <li>Prostokąt (z zaokrąglonymi rogami), elipsa, wielokąt, linia, linia łamana, pióro, odręczne i tekst dowolną zainstalowaną czcionką, także po ścieżce, z literami połączonymi dla czcionek pisanych.</li>
      <li>Gotowe kształty (gwiazda, serce, pierścień, strzałka, koło zębate...) i kody QR.</li>
      <li>Suma, różnica, część wspólna, wykluczenie, odsunięcie, edycja węzłów.</li>
      <li>Wzór z kształtów: wypełnij kształt rzędami małych gwiazdek albo serduszek, każde w całości, z podglądem na żywo.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col"><a href="{{ img }}pen-mode.png"><img loading="lazy" src="{{ img }}pen-mode.png" alt="Tryb pisaka: koło, gwiazda i serce wypełnione wzorami"></a></div>
  <div class="text-col">
    <h3>Rysowanie pisakiem</h3>
    <ul>
      <li>Włóż pisak do oprawki i przełącz narzędzie na pisak: bez przesunięcia noża i bez nadcięcia.</li>
      <li>Kreska na linii, na zewnątrz albo wewnątrz linii, według grubości pisaka.</li>
      <li>Dziewięć wzorów wypełnienia: linie, kratka, fale, zygzak, okręgi, plaster miodu, romby, cegiełki, koncentryczne.</li>
      <li>Zdjęcie jako rysunek: jego jasne i ciemne miejsca z fal sejsmografu, spirali albo kreskowania.</li>
    </ul>
  </div>
</div>

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}colours.png"><img loading="lazy" src="{{ img }}colours.png" alt="Projekt w pięciu kolorach: panel Kolory i logo, każdy kolor osobno"></a></div>
  <div class="text-col">
    <h3>Kilka kolorów, jeden po drugim</h3>
    <ul>
      <li>SVG w kilku kolorach otwiera się w swoich kolorach; podobne są łączone, więc rysuje je jeden pisak. Widzisz i możesz zmienić, co gdzie trafia.</li>
      <li>Panel Kolory: kolejność rysowania, pominięcie koloru, własna grubość pisaka i wzór wypełnienia. Kontur i wypełnienie mogą być dwoma pisakami: czarny kontur, różowe wypełnienie.</li>
      <li>Start idzie kolor po kolorze, z przerwą na włożenie następnego pisaka albo założenie folii w następnym kolorze; punkt zerowy zostaje, więc kolory trafiają jeden na drugi.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col"><a href="{{ img }}to-origin-after.png"><img loading="lazy" src="{{ img }}to-origin-after.png" alt="Projekt dosunięty do punktu zerowego razem z ramką"></a></div>
  <div class="text-col">
    <h3>Układanie bez marnowania folii</h3>
    <ul>
      <li>Przesuwanie, zmiana rozmiaru uchwytami, obrót o dowolny kąt, lustro, wyrównywanie, rozmieszczanie, grupy.</li>
      <li><strong>Do 0,0</strong> dosuwa zaznaczenie albo cały projekt do punktu zerowego, z miejscem na ramkę i nóż.</li>
      <li><strong>Ułóż ciasno</strong>: części obok siebie, obrócone, gdzie lepiej pasują, na jak najkrótszym kawałku folii.</li>
      <li>Kopie w rzędach i kolumnach oraz pasy dla projektów szerszych niż ploter.</li>
      <li>Otwieranie plików SVG i DXF, obrysowanie logo albo obrazu (PNG, JPG) w kształty do cięcia, zapis projektów, cofanie wszystkiego.</li>
    </ul>
  </div>
</div>

## Plotery

| Ploter | Łączy się jako | Stan |
|---|---|---|
| VEVOR KI-375A (tnie 285 mm) | drukarka USB, HPGL | **przetestowany**: tnie czysto |
| Seiki SK-870T (tnie 780 mm, system 6.8H) | drukarka USB, HPGL | **przetestowany**: tnie czysto |
| VEVOR 870 mm (tnie 780 mm) | drukarka USB, HPGL | profil gotowy (ta sama płyta co dwa powyżej) |
| inne VEVOR, Seiki i podobne zamienniki na tej samej płycie | drukarka USB, HPGL | „VEVOR / Seiki, inny model”: ustaw szerokość cięcia; powinien działać tak samo |
| inne plotery z nożem wleczonym na HPGL albo DMPL | drukarka USB albo port szeregowy | dodaj własny profil |

Dotąd Vintyl był używany z tymi ploterami w trybie **drukarki USB**. Drugi
tryb, **Virtual COM** (port szeregowy, inny sterownik), jest przygotowany w
profilach (port, prędkość transmisji, kontrola przepływu), ale nie był
jeszcze sprawdzony na ploterze. Nacisk i prędkość ustawia się na panelu
plotera: te plotery biorą je tylko stamtąd, a Vintyl pokazuje wartości
materiału przed Startem.

<a id="pobierz"></a>

## Pobierz

<div class="platforms">
  <div class="platform">
    <h3>Linux <span class="tag">AppImage</span></h3>
    <p>Jeden plik ze wszystkim w środku, dla większości 64-bitowych Linuksów z ostatnich lat.</p>
    <p><a class="button primary" href="{{ site.repo }}/releases/latest">Najnowsze wydanie</a></p>
    <p>Nadaj mu prawo uruchamiania i uruchom; Vintyl zaproponuje dodanie się do menu aplikacji. Zobacz <a href="{{ '/pl/guide.html#s1' | relative_url }}">Instalację</a>.</p>
  </div>
  <div class="platform">
    <h3>Ze źródeł</h3>
    <p>Python 3.12 lub nowszy i Qt 6 (PySide6).</p>
    <p><a href="{{ site.repo }}#run-it-from-the-source">Jak uruchomić</a> · <a href="{{ site.repo }}/blob/main/CHANGELOG.md">Co nowego</a> · <a href="{{ site.repo }}/blob/main/TODO.md">Co planujemy</a></p>
  </div>
</div>

## Pytania

<div class="faq">
<details><summary>Czy program wysyła nacisk i prędkość do plotera?</summary>
<p>Do tych ploterów nie: biorą one nacisk i prędkość tylko z własnego panelu. Vintyl przed każdym cięciem pokazuje dużymi cyframi wartości materiału, żeby ustawić je na panelu. Przesunięcie noża i nadcięcie Vintyl wlicza sam w ścieżkę noża; na ploterze nie trzeba ich ustawiać.</p></details>
<details><summary>„Brak uprawnień do /dev/usb/lp0”?</summary>
<p>W Linuksie wysyłać do urządzenia mogą tylko członkowie jego grupy: dołącz raz do grupy <code>lp</code> (<code>sudo usermod -aG lp $USER</code>) i zaloguj się ponownie. Pomoc → Dostęp do plotera pokazuje polecenia do skopiowania.</p></details>
<details><summary>Mojego plotera nie ma na liście.</summary>
<p>Jeśli to VEVOR, Seiki albo podobny zamiennik na tej samej płycie, wybierz „VEVOR / Seiki, inny model” i ustaw szerokość cięcia. Daj nam potem znać, jak poszło: Pomoc → Raport diagnostyczny → Zgłoś mój ploter.</p></details>
</div>
