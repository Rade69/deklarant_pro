# Faktura — greška PDF pregleda po fakturama

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- Grana `codex/faktura-toolbar-razmaci`
- `exporters/pdf_faktura_pregled.py`
- `tests/unit/pdf_faktura_pregled_fonts_test.py`

## Status izvora

- Korisnički screenshot greške — aktivan dokaz simptoma.
- `PDFFakturaPregled.export` i `DeclarationDraft` — aktivni izvori uzroka.
- Konzolni log nije bio dostupan; exporter je exception pretvarao u `False`.

## GitNexus impact

Impact za `PDFFakturaPregled.export` je LOW: jedan direktni pozivalac, tri povezana
simbola, jedan modul i nijedan pogođeni izvršni proces.

## Šta je urađeno

Uklonjen je pristup nepostojećem `draft.sifra_deklaracije`. Naslov PDF-a sada sastavlja
šifru iz `deklaracija_tip`, `deklaracija_oznaka` i `deklaracija_a`. Dodat je test koji
kreira stvarni PDF sa fakturom i naimenovanjem.

## Zašto je urađeno

`DeclarationDraft` nikada nije imao polje `sifra_deklaracije`, pa je svaki poziv exporta
padao sa `AttributeError` prije grupisanja i pisanja PDF sadržaja.

## Kako je urađeno

Kanonska polja Rubrike 1 spojena su u naslov izvještaja. Regresioni test koristi stvarne
`DeclarationDraft`, `InvoiceLine` i `NaimenovanjeDraft` objekte i provjerava `%PDF`
zaglavlje nastalog fajla.

## Šta nije dirano

- Struktura tabela i zbirni podaci PDF-a.
- Standardni PDF spiska naimenovanja.
- GUI meni i ostali exporteri.
- `dist_client`, frozen build i glavna `windows` grana.

## Verifikacija

- Novi stvarni PDF regresioni test — 1 passed.
- Četiri ciljana Faktura test fajla — 37 passed.
- `python -m py_compile exporters/pdf_faktura_pregled.py` — prolazi.
- `git diff --check` — bez grešaka.

Postojeći test `test_register_fonts_uses_discovered_directory` pada na Windowsu zbog
ranije POSIX-specifične pretpostavke o putanji `/home/test`; nije povezan sa export fixom.

## Pronađeni problemi

GUI prikazuje samo generičku poruku jer exporter hvata exception i vraća `False`. To nije
mijenjano u ovom uskom bugfixu.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `ee3aa2a` | `fix(faktura): popravi PDF pregled po fakturama` |

## Rizici / ograničenja

Popravka je na posebnoj grani i nije prisutna u postojećem frozen build-u.

## Potreban follow-up

Korisnik treba ponoviti izvoz na stvarnoj deklaraciji. Nakon potvrde granu spojiti u
`windows` i rebuildati aplikaciju.

## Potrebna korisnička potvrda

Potvrditi da `Pregled po fakturama` sada kreira i otvara sačuvani PDF.
