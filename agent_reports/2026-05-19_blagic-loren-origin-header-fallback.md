# Blagic-Loren origin header fallback

## Problem

Nova posiljka u `najavauvoza/LOREN/fwrauniipakingliste` imala je jedan Excel/PDF par gdje zemlje nisu bile ucitane:

- `267VP-2026 SRETO BLAGIC.xlsx`
- `267VP-2026 SRETO BLAGIC.pdf`

Excel fajl u koloni I ima vrijednosti zemlje (`KINA`), ali header kolone nije `Poreklo`, nego pogresno `Tezina `. Parser je zato mapirao obavezne kolone, ali nije prepoznao kolonu porijekla.

## Rjesenje

U `importers/vendors/blagic/blagic_loren_importer.py` dodat je fallback:

- ako header `Poreklo/Porijeklo` nije pronadjen,
- parser gleda kolone iza tarifnog broja,
- kolona se prihvata kao porijeklo ako vecina vrijednosti iz stavki normalizuje u ISO kod zemlje.

Ovim regularni Blagic-Loren fajlovi sa ispravnim headerom ostaju na postojecem putu, a los header iz nove posiljke se pokriva bez hardkodovanja broja fakture.

## Verifikacija

Problematicni fajl:

- prije: `267VP` imao 22/22 stavke bez zemlje,
- poslije: `267VP` ima 22/22 stavke sa `CN`.

Cijeli folder:

- `262VP`: `TR`
- `263VP`: `RS`
- `264VP`: `CN`
- `265VP`: `US`
- `266VP`: `IT`, `SI`
- `267VP`: `CN`
- `268VP`: `CN`

Pokrenuto:

```bash
python -m pytest tests/unit/test_blagic_loren_agent_import.py tests/unit/test_import_validator.py -q
```

Rezultat:

```text
27 passed
```

## Napomena

Kada se kroz `ImportService` uveze prvo PDF, privremeni PDF rezultat i dalje nema zemlje jer PDF ne nosi tarifno/zemlja mapiranje. Nakon uvoza odgovarajuceg Excel fajla vraca se kombinovani rezultat sa zemljama.
