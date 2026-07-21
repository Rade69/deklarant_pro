# Faktura Segment 5 — validacioni prikaz

## Cilj

Učiniti tarifni broj lakšim za poređenje i ublažiti validacione pozadine bez
promjene validacione logike, kolona ili layouta Faktura taba.

## Pogođeno

- `FakturaView._validate_and_color_row` — HIGH, 28 povezanih simbola,
  8 direktnih pozivalaca, 0 execution procesa.
- `ValidationDelegate.paint` — LOW, 0 pozivalaca i 0 execution procesa.

Visok impact prvog metoda dolazi od centralne uloge u svim tokovima punjenja i
provjere Faktura tabele. Promjena ostaje ograničena na literalne boje.

## Plan

1. U delegate rendereru koristiti monospaced font samo za kolonu tarifnog broja.
2. Zamijeniti jarke plave, crvene i žute pozadine blažim nijansama.
3. Pokrenuti `py_compile`, ciljani pytest i offscreen Qt provjeru.
4. Selektivno stageovati samo ovaj segment i provjeriti GitNexus scope.

## Šta NE dirati

- Uslove i prioritet validacionih grana.
- `ValidationColorRole`, tooltipove i cache.
- Country/preference confidence logiku.
- Širinu, redoslijed i broj kolona.
- Paralelne unstaged tarifne izmjene u `faktura_view.py`.

## Konflikti

U `faktura_view.py` postoje paralelne unstaged izmjene tarifne validacije drugog
autora. One nisu u konfliktu sa linijama boja, ali moraju ostati izvan commita.
Važeći scope je isključivo ovaj Segment 5; korisnička potvrda nije potrebna prije
implementacije jer je korisnik već odobrio segmentni nastavak.

