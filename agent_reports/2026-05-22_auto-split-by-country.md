---
date: 2026-05-22
task: Auto-podjela grupnog uvoza po zemljama porijekla
agent: Claude Sonnet 4.6
commit: 8fc02b4
---

# Auto-podjela deklaracija po zemljama porijekla

## Šta je urađeno

Implementirana je funkcionalnost automatske podjele grupnog uvoza faktura
na zasebne deklaracije — po jednoj za svaku grupu zemalja porijekla.
EU zemlja idu zajedno kao jedna deklaracija.

## Kako je urađeno

### Novi fajlovi

| Fajl | Opis |
|------|------|
| `services/faktura/declaration_split_service.py` | Servis za podjelu drafta |
| `gui/widgets/multi_draft_navigator.py` | Navigator widget ◀ ▶ |
| `tests/unit/test_declaration_split_service.py` | 17 testova |

### Izmijenjeni fajlovi

| Fajl | Izmjena |
|------|---------|
| `gui/tabs/faktura_view.py` | Navigator u layout, `_offer_split_by_country()`, `_switch_to_draft()` |

---

### `DeclarationSplitService` — arhitektura

**`declaration_country_group(zemlja)`** — mapira svaku zemlju na grupu:
- EU skup (27 država) → `"EU"`
- Ostalo → šifra (npr. `"TR"`, `"RS"`, `"CN"`)
- Prazno → `""`

**`split_draft_by_country(draft)`** — dijeli draft:
1. Grupiše `invoice_lines` po grupi zemalja
2. Ako samo jedna grupa → vraća `[draft]` bez kopiranja
3. Inače → kopira zaglavlje (shallow copy, bez callbacks/items/weights)
4. Raspodjeljuje `invoice_weights` po grupama:
   - Faktura čije sve stavke idu u jednu grupu → cijela težina toj grupi
   - Mixed faktura (više C/O u jednoj fakturi) → proporcionalno po `iznos`
5. Svaki draft dobija `._country_group` attr za navigator

### `MultiDraftNavigator` widget

QWidget sa framom, smješten između toolbar-a i tabele u FakturaView.
Vidljiv samo kad postoje 2+ drafta (`self.setVisible(len(drafts) > 1)`).

Prikazuje:
```
📂 Deklaracija po zemljama:  ◀  2 od 4 — Turska (TR) • 29 stavki  ▶
                              ○ EU (2)  ● TR (29)  ○ RS (29)  ○ CN (23)
```

Emituje `draft_changed(int)` signal koji FakturaView hvata i poziva
`_switch_to_draft(index)`.

### Hook u `_import_multiple_files()`

Nakon što grupni uvoz završi i prikaz se osvježi, poziva se
`_offer_split_by_country(all_items)`. Ako ima više od 1 grupe,
prikazuje se `QMessageBox.question` — korisnik bira da li želi podjelu.

### `_switch_to_draft(index)`

```python
self.draft = self._multi_drafts[index]
# Resetuj WeightManager na težine novog drafta
# _load_data_from_draft() + _update_status_bar()
```

`self.draft` se jednostavno zamijeni — sve 100+ mjesta u FakturaView
koja čitaju `self.draft` automatski rade sa novim draftom.

## Zašto

Carinska praksa: deklaranti prave zasebnu JCI deklaraciju po zemlji
porijekla robe. Dosad su ručno filtrirali stavke i punili više puta.
Sa ovom funkcijom — jedan uvoz svih faktura + Excel, jedno pitanje,
N deklaracija automatski kreiranih i navigabilnih.

## Primjer iz prakse (KG Fashion, 13 faktura)

Ulaz: 254 stavke, 1 XLS manifest
Izlaz: 5 deklaracija automatski:

| Deklaracija | Stavki | Zemlja |
|-------------|--------|--------|
| BR (Brazil) | 169 | Petite Jolie, Vizzano |
| TR (Turska) | 29 | Bueno, Mod — EUR1 |
| RS (Srbija) | 29 | Jagger |
| CN (Kina) | 23 | Vizzano torbe |
| EU | 2 | Ambitious — EUR1 |

## Testovi

17 novih testova pokrivaju:
- `declaration_country_group` — EU merge, lowercase, prazno
- `count_country_groups` — merge provjera
- `split_draft_by_country` — osnov, EU merge, header kopija
- Raspodjela težina — single i mixed faktura (proporcionalno)
- `group_label` — poznate i nepoznate grupe

**Rezultat: 443 passed (sve)**

## Commit historija

| Hash | Opis |
|------|------|
| `8fc02b4` | feat(import): auto-podjela grupnog uvoza po zemljama porijekla |
