# Agent Report: Tri UX poboljšanja agenta

**Datum:** 2026-05-23  
**Commit:** b1b71a8

---

## Pregled

Implementirana tri poboljšanja iz CODEX prijedloga, redom po prioritetu:

---

## Feature #2 — "Isti izvoznik" badge u TariffValidationDialog

**Fajl:** `gui/tabs/agent/widgets/tariff_validation_dialog.py`

Dijalog istorijske validacije sada prikazuje zeleni badge "✓ Isti izvoznik" pored svakog prijedloga koji dolazi od istog izvoznika kao što je na fakturi. Ovo direktno pokazuje korisnik zašto je prijedlog pouzdan — ranije je sistem bio crna kutija.

Badge se prikazuje samo kad `match.supplier_match == True`, što se sada puni iz `_to_matches(supplier_matched=True)` u `HistoricalTariffSearchService`.

---

## Feature #1 — PreFlightNaimenovanjaDialog

**Novi fajl:** `gui/dialogs/preflight_naimenovanja_dialog.py`  
**Izmjena:** `gui/tabs/faktura_view.py` — `_on_create_naimenovanja()`

Novi modalni dijalog koji se prikazuje PRIJE kreiranja naimenovanja. Zamjenjuje fragmetnarne QMessageBox upozorenja.

**Šta prikazuje:**
- Broj stavki i predviđeni broj naimenovanja (simulira grupisanje)
- Greške: stavke bez tarifnog broja (blokiraju ispravno grupisanje)
- Upozorenja: stavke bez zemlje porijekla, povlastica bez EUR1/PE broja
- Ako je sve uredu — zelena poruka "Sve provjere su prošle"

**Dugmad:** "Nastavi" / "Nastavi svejedno" (ako ima blokatora) / "Odustani"

Grupisanje za predviđeni broj koristi isti ključ kao `CreateNaimenovanjaService._group_lines()`:  
`(tariff_code, origin_country, preference_code, eur1_number)`

---

## Feature #3 — Auto-učenje ručnih ispravki tarife

**Izmjena:** `gui/tabs/faktura_view.py`

Kada korisnik ručno promijeni tarifni broj (kolona 4) u Faktura tabeli:
1. Red se dodaje u `_pending_learn_rows`
2. Nakon debounce timera (200ms), `_auto_learn_edits()` poziva `TariffMappingService.save_mapping()`
3. Na status baru se prikazuje `"💾 Naučeno: [naziv] → [tarifa]"` 3 sekunde, pa se vraća normalna validacija

Nema modala — ne prekida korisnikov rad. Tiho gradi bazu znanja pri svakom ručnom unosu.

---

## Fajlovi izmijenjeni

| Fajl | Promjena |
|------|----------|
| `gui/tabs/agent/widgets/tariff_validation_dialog.py` | "Isti izvoznik" badge |
| `gui/dialogs/preflight_naimenovanja_dialog.py` | novi fajl — PreFlightNaimenovanjaDialog |
| `gui/tabs/faktura_view.py` | pre-flight integracija + auto-učenje |

## Commitovi

| Hash | Opis |
|------|------|
| `b1b71a8` | feat(ux): tri poboljšanja agenta — badge, pre-flight, auto-učenje |
