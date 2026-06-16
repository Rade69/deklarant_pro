# Univerzalna normalizacija tarifnih brojeva — plan

## Cilj
Normalizacija tarifnih brojeva (10→8 cifara, zfill na 4-7 cifara, "/" split) mora se
desiti za SVE parsere, ne samo u GUI putanjama. Korisnik je eksplicitno zahtijevao:
"Ta normalizacija mora biti primjenjena na sve parsere."

## Pogođeno (GitNexus impact)
- `ImportResult` klasa (upstream): **CRITICAL** — 137 impacted, 72 direktnih (sve IMPORT relacije, ne logički pozivači)
- Odluka: NE dirámo `ImportResult.__post_init__` directno
- Umjesto toga: nova privatna metoda `ImportService._normalize_tariffs_in_result()` (0 upstream callera)
  + pozivi na 4 return mjesta u `ImportService.import_file()` (CRITICAL, 13 impacted, ali additive promjena)

## Plan

### Fajlovi (root + dist_client mirror):
1. `services/import_service.py` + `dist_client/services/import_service.py`
   - Dodati privatnu metodu `_normalize_tariffs_in_result(result)` u klasu `ImportService`
   - Pozvati je na 4 return mjesta u `import_file()`:
     - Red 124: `return combined` (Loren/Šumaprom/Invoice+PL kombinovanje)
     - Red 137: `return packing_result` (packing lista)
     - Red 150: `return med_result` (Medicopharm)
     - Red 167: `return result` (registry import)

### Šta NE dirati:
- `ImportResult` dataclass — ne mijenjati `__post_init__`, polja, API
- `_validate_or_raise` — ostaje nepromijenjena
- `_try_combine_with_previous` — ostaje nepromijenjena (normalizacija se dešava na return iz `import_file`)
- GUI-nivo `_normalize_item_tariffs` pozivi u `faktura_view.py` (idempotentna mreža sigurnosti — ostaju)
- `agent_controller.py` normalizacija (commit 289e896 — ostaje kao backup)

### Konflikti:
Nema. Prethodna normalizacija (GUI putanje) je idempotentna — pozivanje dvaput nema efekta.

## Verifikacija
1. `python -m py_compile services/import_service.py`
2. `python -m py_compile dist_client/services/import_service.py`
3. Offscreen test: konstruisati `ImportResult` sa 10-cifrenim kodom → pozvati `import_service.import_file()` mock

## Status: U TOKU
