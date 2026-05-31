# Agent Report — NaimenovanjaView binding refactor

**Datum:** 2026-05-12  
**Zadatak:** Pojednostaviti `gui/tabs/naimenovanja_view.py` bez promjene funkcionalnosti  
**Status:** Završeno

---

## Šta je urađeno

Refaktorisan je unutrašnji data-binding dio klase `NaimenovanjaView`.

Dodati su privatni helperi za:

- čitanje virtualnih i običnih vrijednosti iz `NaimenovanjeDraft`
- upis vrijednosti u `QComboBox`, `QLineEdit` i `QTextEdit`
- specijalni prikaz `le_rubrika40_2` kao šifre bez opisa
- čitanje vrijednosti iz widgeta
- normalizaciju vrijednosti prije upisa u draft
- primjenu master vrijednosti na ostala naimenovanja
- zajednički refresh summary/status prikaza

Javni interfejs nije mijenjan. Nisu mijenjani `.ui` nazivi, signal/slot tokovi, tarifni lookup, XML import, KB sync ni geometrija Qt widgeta.

---

## Kako je urađeno

### `gui/tabs/naimenovanja_view.py`

Uvedeni helperi:

- `_get_item_field_value`
- `_set_widget_value`
- `_set_combo_value`
- `_extract_display_code`
- `_find_combo_index_by_code`
- `_format_line_edit_value`
- `_read_widget_value`
- `_normalize_field_value`
- `_apply_to_other_items`
- `_mark_dirty`
- `_refresh_summary_and_status`

`_load_current_item` je skraćen tako da više ne sadrži inline grananje za tri tipa widgeta.

`_save_current_item` je skraćen tako da ne duplicira čitanje vrijednosti i type conversion logiku.

`_on_rubrika40_2_finished` i `_on_rubrika40_3_finished` koriste zajednički helper za primjenu vrijednosti na ostala naimenovanja.

Rub.44.4 nije prebačen na `_apply_to_other_items`, jer ima poslovno pravilo da se Rub.44 ne smije upisati ako Rub.36 nije popunjena.

---

## Zašto

`NaimenovanjaView` je veliki GUI fajl sa mnogo istorijski akumulirane logike. Najsigurniji refaktor bio je lokalno izdvajanje očigledno ponovljenih obrazaca unutar iste klase, bez pomjeranja u nove module i bez promjene javnog interfejsa.

Odbijene alternative:

- **Razbijanje fajla na više servisa/modula:** prevelik rizik za trenutni zadatak jer bi diralo import granice, Qt inicijalizaciju i signal/slot redoslijed.
- **Refaktor `_setup_rb40_widgets`:** rizično zbog ručne geometrije, custom combo klasa i specijalnog dropdown ponašanja.
- **Generalizacija Rub.44.4 master polja:** nije bezbjedna jer zavisi od Rub.36 poslovnog pravila.

---

## Provjere

| Provjera | Rezultat |
|----------|----------|
| `python -m py_compile gui/tabs/naimenovanja_view.py` | OK |
| `python -m pytest tests/ -q` | 218 passed, 6 skipped |
| GitNexus impact `NaimenovanjaView` | LOW |
| GitNexus detect changes prije commita | risk low, affected processes 0 |

---

## Memorija

Flat memorija:

- `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_naimenovanja-view-binding-refactor.md`

MCP memory:

- `7625899b-3bc1-4efe-a384-9e875501a08f`

---

## Commiti

| Hash | Poruka |
|------|--------|
| `9a0663d` | `refactor(naimenovanja): pojednostavi binding bez promjene ponasanja` |
