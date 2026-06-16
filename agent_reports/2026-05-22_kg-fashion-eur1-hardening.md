---
date: 2026-05-22
task: KG Fashion EUR1 prijedlog, historijske tarife i consumed_paths
agent: Claude Sonnet 4.6
commits: 51ce352, 6dfad8a
---

# KG Fashion — EUR1 hardening i historijske tarife

## Šta je urađeno

Zaokružen EUR1 tok za KG Fashion parser: EUR1 iz XLS manifesta se
više ne šalje direktno kao `has_origin_statement`, nego kao prijedlog
koji korisnik potvrđuje u dijalogu. Dodata auto-popuna tarifa iz baze
znanja za fakture gdje PDF nema HS kod (Jagger, Vizzano).

## Kako je urađeno

### Promjena EUR1 toka

Ranije: `has_origin_statement=True` se postavljao direktno iz manifesta
→ preskakalo se EUR1 dijalog i korisnik nije imao šansu da ispravi.

Sada:
- `ImportResult.has_origin_statement = False` uvijek
- Stavke dobijaju `raw["eur1_suggested"] = True` ako manifest potvrđuje EUR1
- `Eur1QuickDialog` čita taj flag i **auto-čekira checkbox** za tu grupu
- Korisnik mora samo unijeti EUR1 broj i potvrditi — ne bira ručno

### consumed_paths fix

XLS manifest se sad pravilno upisuje u `consumed_paths` unutar
`import_kg_fashion()`. Bez toga agent je procesirao i PDF i XLS
zasebno, što je rezultiralo duplikatima stavki u deklaraciji.

### `_apply_historical_tariff_suggestions()`

Nova funkcija u `kg_fashion_importer.py`:
- Poziva `TariffMappingService.find_mapping()` za svaku stavku bez HS koda
- Minimalna sličnost: `0.92` (konstanta `_HISTORICAL_TARIFF_MIN_SIMILARITY`)
- Upisuje: `tarifni_broj`, `tariff_suffix`, `tariff_similarity`
- Označava izvor: `raw["tariff_source"] = "historical_suggestion"`
- Vraća `(filled, lookup_failed)` za warnings

### warnings[]

`ImportResult.warnings` lista obavještava korisnika o:
- Broju stavki bez tarife u PDF-u
- Broju auto-popunjenih tarifa iz istorije
- Nedostupnosti baze znanja

### XLS parser fix

`_parse_manifest_xls()` je preskakao prazne redove na kraju tablice,
ali sumarne redove (npr. ukupan bruto/neto bez broja fakture) nije
ignorisao. Dodata provjera `has_row_identity` koja skip-uje redove
gdje su sve relevantne kolone prazne.

### Agent worker detekcija

"ptp" i "15467" dodani u listu ključnih riječi za detekciju
KG Fashion manifest XLS fajlova u `ProcessingWorker._is_mapping_xlsx()`.

## Zašto

Klijent prima fakture od Jagger i Vizzano brendova gdje PDF ne sadrži
HS kod (tarifni broj). Deklarant mora ručno tražiti tarifu svaki put.
Sa `_apply_historical_tariff_suggestions()`, sistem automatski predlaže
tarifu iz prošlih deklaracija i jasno označava da je prijedlog —
deklarant samo potvrđuje ili ispravlja, umjesto da traži od nule.

EUR1 auto-čekiranje smanjuje klikove: manifest već zna koje fakture
imaju EUR1, pa nema razloga da korisnik to ručno označava.

## Testovi

| Test fajl | Testovi | Pokriva |
|-----------|---------|---------|
| `test_kg_fashion_manifest.py` | 5 | consumed_paths, EUR1 prijedlog, zemlja prioritet, warnings, historijska tarifa |
| `test_eur1_quick_dialog.py` | 1 novi | auto-čekiranje iz eur1_suggested flaga |
| `test_agent_processing_worker_sort.py` | 1 novi | ptp/15467 detekcija manifest fajlova |

Ukupno: **20 passed**

## Commit historija

| Hash | Opis |
|------|------|
| `51ce352` | feat(import): kg-fashion EUR1 prijedlog, historijske tarife i consumed_paths |
| `6dfad8a` | chore: ažuriraj GitNexus statistike i dodaj mcp-gitnexus report |
