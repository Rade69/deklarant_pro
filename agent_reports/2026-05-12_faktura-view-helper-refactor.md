# Agent Report — FakturaView helper refactor

**Datum:** 2026-05-12  
**Zadatak:** Pojednostaviti `gui/tabs/faktura_view.py` bez promjene funkcionalnosti  
**Status:** Završeno

---

## Šta je urađeno

Refaktorisan je dio `FakturaView` klase kroz male privatne helpere.

Dodati su helperi za:

- zajedničko emitovanje `data_changed` + `on_dirty`
- postavljanje `invoice_number` na listu uvezenih stavki
- prepoznavanje istog kombinovanog invoice para
- dodavanje sekcije o uvezenim Excel/PDF fajlovima u poruke
- ponovljenu poruku kada nema stavki za export

Uklonjeni su lokalni importi koji su već dostupni na module nivou (`re`, `logging`) i `traceback.print_exc()` je zamijenjen sa `logger.exception`.

---

## Kako je urađeno

### `gui/tabs/faktura_view.py`

Uvedeni helperi:

- `_notify_data_changed`
- `_assign_invoice_name`
- `_is_same_combined_invoice`
- `_append_imported_files_message`
- `_show_no_export_items`

Primijenjeni su samo na mjesta gdje je obrazac već postojao i gdje se ponašanje može očuvati bez promjene redoslijeda ključnih poslovnih koraka.

`_on_import_finished` je skraćen, ali nije strukturno razbijen u nove servise. Izvučena je samo čista lokalna logika:

- setovanje `invoice_number`
- fuzzy provjera da li je import isti kombinovani invoice
- file-count tekst u porukama

Export metode su zadržale svoje specifične uslove. Generalizovana je samo poruka za slučaj kada nema stavki.

---

## Zašto

`faktura_view.py` je veliki GUI fajl od oko 3500 linija. Najveći rizik je u import toku, gdje se prepliću assembly mode, obični import, kombinovani PDF/Excel parovi, težine i povlastice. Zato je izabran minimalni refaktor koji smanjuje ponavljanje, ali ne pomjera poslovne odluke.

Odbijene alternative:

- **Razbijanje `_on_import_finished` na više većih metoda:** prevelik rizik jer je metoda vezana za redoslijed import side-effecta.
- **Refaktor `_on_calculate_masses`:** logika je duga, ali poslovno osjetljiva zbog različitih scenarija težina.
- **Generalizacija PDF/Excel/Pregled export toka:** export metode imaju različite preduvjete i poruke; generalizovana je samo zajednička prazna-lista poruka.

---

## Provjere

| Provjera | Rezultat |
|----------|----------|
| `python -m py_compile gui/tabs/faktura_view.py` | OK |
| `git diff --check -- gui/tabs/faktura_view.py` | OK |
| `python -m pytest tests/ -q` | 218 passed, 6 skipped |
| GitNexus impact `FakturaView` | alat timeout; Cypher incoming upit bez direktnih referenci |
| GitNexus detect changes prije commita | risk low, affected processes 0 |

---

## Memorija

Flat memorija:

- `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_faktura-view-helper-refactor.md`

MCP memory:

- `9b637ca1-3a84-4210-a678-cba3381645fb`

---

## Commiti

| Hash | Poruka |
|------|--------|
| `7244ded` | `refactor(faktura): izdvoji ponavljanja u view helperima` |
