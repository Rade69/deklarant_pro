## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Izmjena: `importers/vendors/cmana/cmana_pdf_parser.py` + `dist_client/` kopija.

## Status izvora
Nastavak `agent_reports/2026-08-04_importers-zatvaranje-preostalih-nepoznanica.md`, koji je
nalaz identifikovao ali namjerno ostavio korisniku na odluku (dira tarifnu poslovnu logiku).
Korisnik je eksplicitno odobrio: "Podigni kako je i kod drugih a fakture ću naći da ih pogledaš".

## Impact analiza
`gitnexus_impact` na `get_tariff_codes_for_product_name`: risk LOW, 1 direktan pozivalac
(`parse_cmana_pdf` u istom fajlu), dalje kroz `_parse_cmana` → `parse_smart_pdf` (glavni
dispatch). `affected_processes` prazno (samo statička veza, ne narušava postojeći izvršni tok).

## Reprodukcija prije izmjene
N/A za ovaj fix specifično — bug (prag `> 0.0`/`> 0.25`) je već dokumentovan i pokazan čitanjem
koda u prethodnom izvještaju. Nema realne CMANA fakture za live prije/poslije test u ovoj sesiji
(korisnik je najavio da će dostaviti naknadno).

## Šta je urađeno
1. Dodat modul-level `_TARIFF_MIN_SIMILARITY = 0.92` u `cmana_pdf_parser.py`, sa komentarom koji
   referiše AGENTS.md standard i objašnjava zašto (isti kao `kg_fashion_importer.py`).
2. Zamijenjen `if best_match and best_score > 0.0:` (interno u `get_tariff_codes_for_product_name`)
   sa `if best_match and best_score >= _TARIFF_MIN_SIMILARITY:`.
3. Zamijenjen `if tariff_by_name and similarity > 0.25:` (na pozivnom mjestu u `parse_cmana_pdf`)
   sa `if tariff_by_name and similarity >= _TARIFF_MIN_SIMILARITY:` — usklađeno sa istim
   konstantom umjesto duplirane, slabije magic-number provjere.
4. `py_compile` na oba fajla — OK. Puna `pytest tests/ -q` (bez DB-zavisnih) — 1663 passed,
   identičan pre-postojeći broj fail-ova (3, nepovezano).
5. `dist_client/` sync uz očuvanu CRLF konvenciju, potvrđena sadržajna identičnost.
6. `gitnexus_detect_changes` prije commit-a — risk low, scope tačno kao očekivano (samo CMANA
   fajl + pre-postojeći nepovezan WIP).
7. Commit `7f027c4`.

## Zašto je urađeno
Korisnik je eksplicitno odobrio podizanje praga na isti nivo kao ostali dobavljači (projektni
standard 0.92), sa napomenom da će dostaviti stvarne CMANA fakture za naknadnu provjeru.

## Kako je urađeno
Minimalna, ciljana izmjena — jedna nova konstanta, dvije linije promijenjene sa magic brojeva na
referencu te konstante. Nema dodatnih promjena (npr. nije dodana `tariff_similarity`/
`raw["tariff_source"]` transparentnost kakvu ima `kg_fashion_importer.py` — to nije bilo
eksplicitno traženo, van scope-a ovog fix-a).

## Šta nije dirano
- `get_tariff_codes_for_invoice()` (druga DB funkcija u istom fajlu, mapiranje po tačnoj šifri
  ne po fuzzy nazivu) — nije imala problem sa pragom, nije dirana.
- `_parse_number_cmana()`, `_CMANA_PRODUCT_TARIFFS` mapa — nedirano.
- Transparentnost porijekla tarife (`tariff_similarity` polje, `raw["tariff_source"]`) kakvu ima
  `kg_fashion_importer.py` — NIJE dodano ovom izmjenom, jer nije bilo eksplicitno traženo. Vidi
  "Potreban follow-up".

## Verifikacija
`py_compile` OK oba fajla. Puna `pytest tests/ -q -k "not test_db_..."` — 1663 passed, identičan
baseline. `dist_client/` sadržajna identičnost potvrđena (CRLF/LF normalizovano poređenje).
**Nije verifikovano na realnoj CMANA fakturi** — korisnik će dostaviti naknadno.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: GitNexus impact LOW, minimalna izmjena (2 linije + 1 konstanta), ne mijenja postojeće
  ponašanje osim u smjeru "manje lažnih tarifnih pogodaka" (strože, ne popustljivije). Preporučuje
  se da korisnik potvrdi na realnoj CMANA fakturi kad je dostavi — vidi "Potrebna korisnička
  potvrda".

## Pronađeni problemi
Nema novih — ovo zatvara nalaz iz prethodnog izvještaja.

## Odbačene opcije
- Opcija: dodati i `tariff_similarity`/`raw["tariff_source"]` transparentnost po uzoru na
  kg_fashion, u istoj izmjeni.
- Zašto je razmatrana: bila bi konzistentna sa "kako je i kod drugih" duhom zahtjeva.
- Zašto je odbačena (za sada): korisnikov zahtjev je bio specifično o pragu ("Podigni kako je i
  kod drugih"), ne o cijelom transparentnost-obrascu; dodavanje bez eksplicitnog traženja bi bilo
  širenje obima van onoga što je zatraženo (AGENTS.md: "ne dodavati... beyond what the task
  requires"). Lako se doda naknadno ako korisnik to poželi.
- Kada odluku ponovo otvoriti: ako korisnik pri pregledu realnih CMANA faktura primijeti da bi mu
  koristilo da vidi koliko je pouzdan fuzzy-match rezultat (isto kao kod kg_fashion).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `7f027c4` | `fix(importers): CMANA fuzzy-match tarifni prag podignut na 0.92` |

## Rizici / ograničenja
Efekat ove izmjene je da CMANA fuzzy-match po nazivu proizvoda sada ČEŠĆE vraća prazan tarifni
broj (kad sličnost ne dosegne 92%) nego prije — ovo je namjeravano (manje lažnih pogodaka), ali
znači da će više CMANA stavki ostati BEZ auto-popunjenog tarifnog broja i tražiti ručni unos.
Ovo je ispravan kompromis po projektnom standardu, ali korisnik treba biti svjestan efekta.

## Potreban follow-up
1. Verifikacija na realnoj CMANA fakturi kad korisnik dostavi (vidi "Potrebna korisnička potvrda").
2. Razmotriti dodavanje `tariff_similarity`/`raw["tariff_source"]` transparentnosti po uzoru na
   kg_fashion (odbačena opcija iznad) — ako korisnik to zatraži nakon što vidi efekat na realnim
   podacima.

## Potrebna korisnička potvrda
Kad korisnik dostavi realne CMANA fakture: potvrditi da (a) fuzzy-match i dalje pogađa tarife za
poznate/slične proizvode (ne prestrogo), i (b) da za nepoznate/različite proizvode sada ispravno
ostaje prazno umjesto da tiho upiše pogrešnu tarifu.
