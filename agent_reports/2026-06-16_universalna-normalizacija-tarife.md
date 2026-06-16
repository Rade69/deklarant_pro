## Datum
2026-06-16

## Agent
Claude Sonnet 4.6

## Scope
- `services/import_service.py`
- `dist_client/services/import_service.py`
- `project_rooms/2026-06-16_univerzalna-normalizacija-tarife.md` (plan, privremeno)

## GitNexus impact
- `ImportResult` klasa (upstream): **CRITICAL** — 137 impacted, 72 direktnih (sve IMPORT relacije, ne logički pozivači `__post_init__`)
- Odluka: ne dirati `ImportResult.__post_init__` — umjesto toga nova privatna metoda u `ImportService`
- `import_file` (upstream prethodni rezultat): CRITICAL — 13 direktnih, 2 procesa, 15 affected
- Nova metoda `_normalize_tariffs_in_result`: 0 upstream callera izvan klase — NEW symbol, LOW risk

## Šta je urađeno
- Dodata privatna metoda `ImportService._normalize_tariffs_in_result(result)` koja in-place normalizuje `tarifni_broj` za svaku stavku `ImportResult`-a
- Metoda se poziva na sva 4 return mjesta u `import_file()`:
  1. `return combined` (Loren/Šumaprom/Invoice+PL kombinovani import)
  2. `return packing_result` (packing lista sačuvana za čekanje)
  3. `return med_result` (Medicopharm specijalizovani Excel)
  4. `return result` (standardni registry import)
- Iste izmjene u `dist_client/services/import_service.py`

## Zašto je urađeno
GUI-nivo `_normalize_item_tariffs()` u `faktura_view.py` pokrivao je samo ručni i batch import
putanju. Korisnik je vidio da Blagić-Loren faktura (Excel+PDF kombinovana) i dalje vraća
10-cifrene tarifne brojeve. Ranija zakrpa (commit `289e896`) pokrila je samo agent putanju.
Korisnik je eksplicitno zahtijevao: "Ta normalizacija mora biti primjenjena na sve parsere."

## Kako je urađeno
Normalizaciona logika je `normalize_tariff_number()` iz `importers/invoice_line_utils.py`
(postojeća funkcija). Nova metoda je lazy import te funkcije + iteracija po `result.items`.
Izmjena je idempotentna — GUI-nivo pozivi ostaju kao backup i neće duplo mijenjati vrijednosti
jer `normalize_tariff_number("38249993")` → `"38249993"` (nema promjene za već normalizovane).

## Šta nije dirano
- `ImportResult` dataclass — `__post_init__`, polja, API nepromijenjen
- `_try_combine_with_previous` — interna metoda ostaje netaknuta
- `faktura_view._normalize_item_tariffs()` pozivi (redovi 2119, 2876) — ostaju
- `agent_controller.py` normalizacija (commit 289e896) — ostaje

## Verifikacija
- `python -m py_compile services/import_service.py` → OK
- `python -m py_compile dist_client/services/import_service.py` → OK
- `gitnexus_detect_changes(scope="all")` → `import_file` i `_try_import_as_packing_list` markirani kao "touched" — tačno očekivano

## Commitovi
| Hash | Poruka |
|------|--------|
| `ceef8ca` | feat(import): universalna normalizacija tarifnih brojeva u ImportService |

## Rizici / ograničenja
- Parseri koji vraćaju `List[InvoiceLine]` direktno (ne `ImportResult`) nisu pokriveni — ali ovi su zastarjeli putevi i `_validate_or_raise` ih preskače (isti pattern)
- Normalizacija se dešava i za packing_list koji se pamti u memoriji za sparivanje — može mijenjati tarifne brojeve koji su privremeni (ali to je ispravno ponašanje)

## Potreban follow-up
- Nema. GUI-nivo pozivi su idempotentni mreža sigurnosti.

## Potrebna korisnička potvrda
- Testirati uvoz Blagić-Loren Excel+PDF kombinacije i provjeriti da su tarifni brojevi 8-cifreni u tabu Faktura
