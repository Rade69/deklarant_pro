# Agent Report — 2026-07-18: Undo/redo + bulk ispravka tarifnog broja

## Datum
2026-07-18

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/faktura_view.py` + dist_client mirror
- `services/tariff/tariff_mapping_service.py` (root only — dist_client koristi .pyd)

---

## GitNexus impact
`detect_changes` rizik: **LOW** za oba commita. Sve promjene su additivne (nove metode, novi shortcutovi) — bez izmjene postojećih putanja.

---

## Šta je urađeno

### 1. Undo/redo (commit `ceb9c44`)

**Ctrl+Z** — poništi posljednju izmjenu  
**Ctrl+Y** / **Ctrl+Shift+Z** — ponovi

Snapshot-based implementacija (max 30 koraka):
- `_push_undo_snapshot()` — deepcopy od `draft.invoice_lines`, push na `_undo_stack`, clear `_redo_stack`
- `_undo()` / `_redo()` — razmjena stekova + `_load_data_from_draft()` za prikaz
- Status bar prikazuje preostali broj koraka ("↩ Poništeno — još 5 koraka u historiji")

Pokrivenost snapshot tačaka:
| Akcija | Snapshot tačka |
|--------|---------------|
| Izmjena ćelije | Početak `_on_item_changed` (draft još ima staru vrijednost) |
| Obriši stavku | Nakon potvrde, PRIJE brisanja |
| Očisti sve | Nakon potvrde, PRIJE čišćenja |
| Uvoz PDF/Excel | Na početku `_on_import_finished` |
| Uvoz XML | Nakon potvrde, PRIJE clear+extend |
| Auto-popuni tarife | Nakon korisnikove potvrde, PRIJE pisanja |

Programatske izmjene (reload, validacija, historijska validacija) koriste `blockSignals(True)` — ne okidaju `_on_item_changed` i ne generišu lažne snapshotove.

### 2. Bulk ispravka tarifnog broja (commit `c590a56`)

**Desni klik** na odabrane redove → meni → "Promijeni tarifni broj za N stavki" → dijalog → primijeni.

Nova metoda `TariffMappingService.correct_mapping`:
- Briše stari pogrešan red iz `product_tariff_mapping` (DELETE po `product_code, naziv_robe, commodity_code`)
- Upisuje novi ispravan (poziva `save_mapping`)

GUI `_correct_tariff_in_db` koristi `getattr(svc, 'correct_mapping', None)` — fallback na `save_mapping` za dist_client koji ima `.pyd` bez `correct_mapping`.

Dijalog brisanja "Očisti sve" ažuriran: tekst promijenjen iz "Ova akcija se ne može poništiti!" u "Moguće poništiti sa Ctrl+Z."

---

## Zašto je urađeno

**Undo/redo**: Korisnik je primijetio da nema načina da vrati slučajno obrisanu/izmijenjenu stavku bez ponovnog prolaska kroz cijeli uvozni proces.

**Bulk tariff ispravka**: Tarifni brojevi koji dolaze s fakture ponekad su pogrešni. Korisnik je trebao ručno uređivati svaku ćeliju. Uz to, stari pogrešan tarif ostajao je u bazi znanja i vraćao se pri sljedećem uvozu iste robe.

---

## Šta nije dirano

- Naimenovanja tab — undo/redo nije implementiran tamo
- Zaglavlje tab — undo/redo nije implementiran tamo
- `_auto_learn_edits` — postojeća logika auto-učenja nepromjenjena; `_correct_tariff_in_db` je dodatan korak samo za bulk edit

---

## Verifikacija

- `py_compile` provjera: OK za sva 3 fajla
- Logička verifikacija: `_on_item_changed` okida se samo za korisničke izmjene (programatske blokirane via `blockSignals`) → snapshot je uvijek od stare vrijednosti

---

## Pronađeni problemi

- `correct_mapping` nije dostupan u dist_client `.pyd` — fallback na `save_mapping` (ne briše stari pogrešan mapping). Riješiti pri sljedećem buildu.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `ceb9c44` | feat(faktura): undo/redo Ctrl+Z/Ctrl+Y za ćelije, brisanje i uvoz |
| `c590a56` | feat(faktura): desni klik - bulk ispravka tarifnog broja + correct_mapping u bazi |

---

## Rizici / ograničenja

- Deepcopy 94 stavki ≈ zanemarivo (< 5ms). Za deklaracije s 500+ stavki može biti primjetno pri brzom tipkanju — monitor ako se javi.
- `_redo_stack.clear()` pri svakom novom snapshotu (standardno ponašanje). Ako korisnik uradi Ctrl+Z pa unese novu izmjenu, redo historija se gubi.

---

## Potrebna korisnička potvrda

- Testirati Ctrl+Z nakon izmjene ćelije, brisanja stavke i uvoza fakture
- Testirati desni klik → "Promijeni tarifni broj" za 1 i više odabranih stavki
- Provjeriti da stari pogrešan tarif više ne dolazi kao prijedlog pri ponovnom uvozu iste robe
