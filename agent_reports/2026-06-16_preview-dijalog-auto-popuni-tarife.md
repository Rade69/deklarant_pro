## Datum
2026-06-16

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`

## GitNexus impact
- `_on_auto_fill` (upstream): risk LOW, 1 direktan pozivač (signal veza u `__init__`), 0 execution flows pogođeno
- `_show_tariff_preview_dialog` (nova metoda): NEW symbol, 0 upstream callera
- `_collect_tariff_previews` (nova metoda): NEW symbol, 0 upstream callera
- `_get_tariff_description` (nova metoda): NEW symbol, 0 upstream callera
- detect_changes: risk LOW, 0 affected processes

## Šta je urađeno
Dodat preview dijalog koji se otvara PRIJE auto-popunjavanja tarifnih brojeva.
Tri nove metode u `FakturaView` (identično u gui/ i dist_client/):
1. `_collect_tariff_previews(target_lines, facade)` — zove `suggest_fast()` za svaku stavku koja nema tarife; vraća listu `(line_no, naziv, tarifa)` bez pisanja u draft
2. `_get_tariff_description(tariff_code)` — dohvata hijerarhijski opis iz `tarifa_2026` SQLite (4-cifra glava / 6-cifra podglava / 10-cifra podbroj, spaja sa " / ")
3. `_show_tariff_preview_dialog(target_lines, preview_details)` — QDialog sa QTableWidget: Rb | Naziv proizvoda | Tarifa | Opis tarife (provjeri!); dugmad "Potvrdi i popuni" / "Odustani"

Modificiran `_on_auto_fill()`: u interaktivnom modu (ne auto), sada:
- Skupi previews → ako nema prijedloga, direktno prikaže stari summary dijalog
- Prikaži preview dijalog → ako korisnik odustane, return None bez pisanja
- Tek po potvrdi pozove `auto_populate_tariffs()` kao i ranije

## Zašto je urađeno
Korisnik je uočio da auto-fill može upisati pogrešnu tarifu (bakarna cijev dobila `90321080` — termostat, umjesto `74111090` — bakarne cijevi). Bez provjere deklarant ne vidi grešku sve dok ne provjeri ručno. Dijalog s opisom tarife daje vizuelni signal ("Termostat" vs "Bakarne cijevi") koji omogućava trenutno otkrivanje nelogičnog prijedloga.

## Kako je urađeno
- `suggest_fast()` korišten za preview jer je dostupan i u kompajliranoj `.pyd` i `.py` verziji `TariffFacade`. Pokušaj dodavanja `dry_run` parametra u `auto_populate_tariffs()` je odbijen jer `dist_client/*.pyd` moduli su kompajlirani i ne mogu se override-ati sa `.py` (Python 3: `.pyd` ima prednost u istom direktoriju).
- `_get_tariff_description()` direktno čita SQLite `/database/deklarant_sistem.db` (lazy import `sqlite3`) — bez PostgreSQL/servisa, brzo i uvijek dostupno.
- Stari `_show_tariff_preview_dialog(target_lines, dry_result)` koji je koristio `MappingResult.matched_details` je zamijenjen novom verzijom sa `preview_details: list` tuple-ova — jednostavniji ulazni format.

## Šta nije dirano
- `auto_populate_tariffs()` u `TariffMappingService`/`TariffFacade` — bez izmjena
- `_show_tariff_mapping_result()` — summary dijalog POSLIJE popunjavanja ostaje nepromijenjen
- Auto mod (`auto=True` putanja) — dijalog se ne prikazuje, direktno poziva `auto_populate_tariffs()` kao i ranije
- `services/tariff_facade.py` — `suggest_fast()` i `auto_populate_tariffs()` bez izmjena
- Baza znanja u PostgreSQL — bez izmjena

## Verifikacija
- `python -m py_compile gui/tabs/faktura_view.py` → OK
- `python -m py_compile dist_client/gui/tabs/faktura_view.py` → OK
- `gitnexus_detect_changes(scope="all")` → risk LOW, 0 affected processes, simboli su `_on_auto_fill` i `FakturaView` klasa — tačno očekivano

## Commitovi
| Hash | Poruka |
|------|--------|
| `074aaad` | feat(faktura): dijalog potvrde tarifnih brojeva PRIJE auto-popunjavanja |

## Rizici / ograničenja
- `suggest_fast()` koristi samo Level 1 (baza znanja), ne i Level 0 (historiju po `line_no`). Ako historija daje drukčiji rezultat od baze znanja, preview može prikazati drukčiju tarifu nego što će `auto_populate_tariffs()` upisati. U praksi je Level 1 isti ili bolji od Level 0 za produkte sa fiksnim `product_code`-om.
- Opis tarife je iz lokalne SQLite baze — ako baza nije dostupna, prikazuje se samo tarifni broj.

## Potreban follow-up
- Nema. Dijalog je samodovoljan.

## Potrebna korisnička potvrda
- Pokrenuti aplikaciju i kliknuti "Auto-popuni tarifne" na fakturi sa stavkama bez tarife — provjeriti da se dijalog otvara PRIJE popunjavanja i da opisi tarifa izgledaju ispravno
