---
date: 2026-05-22
task: KG Fashion PDF + XLS manifest parser
agent: Claude Sonnet 4.6
commit: 4f4901b
---

# KG Fashion Parser — Agent Report

## Sta je uradjeno

Kreiran specijalizovani importer za fakture od **"K... G... FASHION" D.O.O.** Cacak.
Jedan parser pokriva sve brendove: Petite Jolie, Vizzano, Benetton, Sisley, Ambitious,
Kese/Ciklopak, Bueno, Mod 21016, Jagger i ostale.

Integrisana podrska za XLS transport manifest koji sadrzi EUR1 i tezine po posiljkama.

## Kako je uradjeno

### Novi fajlovi
| Fajl | Opis |
|------|------|
| `importers/vendors/kg_fashion/__init__.py` | Package init |
| `importers/vendors/kg_fashion/kg_fashion_importer.py` | Glavni parser (551 linija) |

### Izmijenjeni fajlovi
| Fajl | Izmjena |
|------|---------|
| `importers/smart_pdf_importer.py` | Dodana detekcija "kg_fashion" formata i routing |

### PDF parser — tehnicka arhitektura

Format tabele u svim fakturama:
```
Rb. | Sifra artikla | Naziv | Boja | Tip | Kom-Par | Pol | Sastav | HS | CO | Qty | Price | CUR | Amount | CUR
```

Parsiranje radi od **desna prema lijevo**:
1. `_TAIL_RE` hvata `qty price CUR amount CUR` sa kraja linije
2. Zadnji token preostale linije → C/O detekcija (2-slovni ISO ili puno ime drzave)
3. Prethodni token → HS kod (6-12 cifara)
4. Pronalazak `KOM` ili `PAR` (od desna) → jedinica mjere
5. Sve do KOM/PAR = `code` (prvi token) + `naziv` (ostatak)

### XLS Manifest parser

Fajl: `15467- PTP 11.05.2026..xls` (transport manifest)

Kolone koje se citaju:
- `RACUN` (kol 2): broj fakture → mapira na PDF (25-NNN/2026 → NNN)
- `C/O` (kol 13): zemlja porijekla po posiljci
- `EUR1` (kol 14): EUR1 obrazac → `has_origin_statement=True`
- `Bruto/Neto` (kol 15-16): tezine po posiljci (sumiraju se po fakturi)

Auto-detection: trazi `*.xls`/`*.xlsx` sa "PTP" ili "15467" u imenu, u istom folderu kao PDF.

## Zasto

Klijent "PRET A PORTER" DOO Banja Luka redovno prima fakture od KG Fashion za
razlicite brendove modne odjece i obuce. Svi racuni imaju identican format ali
razlicite brendove. Jedan universal parser eliminise potrebu za posebnim parserom
po brendu.

EUR1 je kljucan za deklaraciju — fakture sa EUR1 imaju preferencijalno porijeklo
(nulta carina u CEFTA zoni). Bez ovog podatka, deklarant mora rucno unijeti
oznaku preferencije.

## Rezultati testiranja

Testirano na 13 faktura iz `/home/radovan/Downloads/fwfakturekojepraterobupretaporter/`:

| Faktura | Stavki | Valuta | EUR1 |
|---------|--------|--------|------|
| RAC.284 - Petite Jolie | 3 | EUR | - |
| RAC.285 - Petite Jolie | 156 | EUR | - |
| RAC.287 - Vizzano | 7 | **USD** | - |
| RAC.288 - Vizzano | 1 | **USD** | - |
| RAC.289 - Vizzano | 2 | **USD** | - |
| RAC.290 - Benetton | 13 | EUR | - |
| RAC.291 - Sisley | 10 | EUR | - |
| RAC.292 - Ambitious | 2 | EUR | **EUR1 (PT)** |
| RAC.294 - Kese/Ciklopak | 2 | EUR | - |
| RAC.296 - Bueno | 13 | EUR | **EUR1 (TR)** |
| RAC.297 - Mod 21016 | 16 | EUR | **EUR1 (TR)** |
| RAC.298 - Jagger | 8 | EUR | **EUR1 (RS)** |
| RAC.302 - Jagger | 21 | EUR | - |
| **UKUPNO** | **254** | | **4 sa EUR1** |

## Poznata ogranicenja

- PETITE JOLIE kodovi su nepotpuni: "PJ11307-PETITE" umjesto "PJ11307-PETITE JOLIE"
  (PDF wrapping — JOLIE se prelama u novu liniju, ignorise se)
- VIZZANO kodovi slicno truncirani zbog dugih sifri i PDF preloma
- KESE kod: "KESE" umjesto "KESE AVG 400X500" (zbog first-token pristupa)
- Za fakture bez HS koda u PDF-u (JAGGER 298/302), tarifa mora biti rucno unesena

## Commit historija

| Hash | Opis |
|------|------|
| `4f4901b` | feat(import): dodaj KG Fashion parser sa EUR1 podrskom |
