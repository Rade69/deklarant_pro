## Datum

2026-07-23

## Agent

OpenAI Codex

## Scope

- `gui/main_window.py`
- `dist_client/gui/main_window.py`
- `tests/unit/test_keyboard_navigation.py`
- `docs/UPUTSTVO_TASTATURNA_NAVIGACIJA.md`
- `docs/CONTEXT.md`

## GitNexus impact

Procjena za `MainWindow` bila je MEDIUM: šest direktnih uvoznika i ukupno 14
tranzitivno povezanih fajlova, bez pogođenih poslovnih procesa. Staged provjera
nakon izmjene nije prijavila promijenjene indeksirane procese.

## Šta je urađeno

Uveden je `F6` za direktan ulazak iz forme u gornji toolbar aktivne kartice.
Kada dugme ima fokus, `Left/Right` i `A/D` mijenjaju dugme, `Home/End` biraju
prvo ili posljednje, `Enter/Space` aktiviraju dugme, a `Esc` vraća fokus na
prethodnu kontrolu. Onemogućena dugmad se preskaču.

## Zašto je urađeno

Standardni `Tab` lanac na velikim obrascima ne omogućava praktičan i pouzdan
povratak u toolbar. `F6` daje direktan ulaz bez presretanja običnih strelica ili
slova tokom unosa podataka.

## Kako je urađeno

Centralni `MainWindow` pronalazi akcione trake aktivne kartice, pamti prethodni
fokus i postavlja event filter samo na dostupna toolbar dugmad. Izvorna i
Windows runtime kopija ostale su usklađene.

## Šta nije dirano

- Nije mijenjan layout ni QSS.
- Nisu mijenjani signali, slotovi ni poslovna logika dugmadi.
- Obični `W/S` i strelice nisu globalno presretnuti.
- Nepovezane postojeće izmjene nisu uključene u commit.

## Verifikacija

- `python -m pytest tests/unit/test_keyboard_navigation.py -q`: 4 testa prošla.
- `python -m py_compile` prošao za izmijenjene Python fajlove.
- `git diff --check` prošao.
- Pre-commit provjera prošla.

## Pronađeni problemi

Projektni virtualni interpreter nije prisutan u ovoj radnoj kopiji, pa su
testovi pokrenuti dostupnim sistemskim Pythonom 3.14 sa PySide6 6.11.1.

## Konflikti / kontradiktorni izvori

Nema konflikta. Prethodni standard je namjerno izbjegavao globalno presretanje
običnih slova i strelica; nova navigacija ih koristi samo dok toolbar dugme ima
fokus.

## Commitovi

| Hash | Poruka |
|---|---|
| `0883062` | `feat(gui): omogući ulazak u toolbar tastaturom` |

## Rizici / ograničenja

Kartice bez definisanog gornjeg akcionog toolbara ne mijenjaju fokus na `F6`.

## Potreban follow-up

Nije potreban.

## Potrebna korisnička potvrda

Ručno provjeriti osjećaj kretanja kroz toolbar na karticama Faktura,
Naimenovanja, Zaglavlje i Šifrarnici.
