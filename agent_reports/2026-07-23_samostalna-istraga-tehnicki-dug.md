# Agent Report: Samostalna istraga — tehnicki dug, mrtav kod i uski grla

**Datum**: 2026-07-23
**Agent**: Pi

---

## Sazetak

Ova istraga je obuhvatila 1.425 Python fajlova (root, bez dist_client/.venv) kroz
vise tehnika: AST analiza velicine funkcija, grep za obrasce tehnickog duga,
staticka analiza importa i provjera konzistentnosti.

Pronadjeno je **11 nalaza** u 6 kategorija, od cega 3 HIGH, 4 MEDIUM i 4 LOW.

---

## 1. Prevelike klase/fajlovi — HIGH

Cetiri fajla su drasticno prevelika i predstavljaju sustinski tehnicki dug.
Svaki od njih krsi SRP (Single Responsibility Principle) i otezava:
- testiranje (tesko je mock-ovati dio klase)
- citanje (vise od 100 metoda u jednom fajlu)
- paralelni rad (vise developera ne moze raditi na istom fajlu bez konflikta)

### 1a) `gui/tabs/faktura_view.py` — 5.563 linije, 123 metode

- **Opis**: Najveci fajl u projektu. Sadrzi: tabelu, toolbar, status bar, import
  pipeline, validaciju, undo/redo, auto-ucenje, kontekstni meni, analizu, PDF
  export, i jos desetine funkcionalnosti — sve u jednoj klasi `FakturaView`.
- **Posljedice**: Svaka izmjena nosi rizik od loma nepovezane funkcionalnosti.
  Testovi su teski (potrebno je instancirati citav View).
- **Prijedlog**: Podijeliti na:
  - `FakturaView` (orchestration, signali)
  - `FakturaToolbar` (dugmad, sekcije)
  - `FakturaTable` (tabela, validacija, bojenje)
  - `FakturaImportHandler` (import pipeline, batch obrada)
  - `FakturaUndoManager` (undo/redo)

### 1b) `gui/tabs/naimenovanja_view.py` — 3.780 linija, 110 metoda

- **Opis**: Drugi najveci fajl. Upravlja prikazom, editovanjem, grupisanjem,
  PDF/Excel exportom i validacijom naimenovanja.
- **Prijedlog**: Izdvojiti `NaimenovanjaTable`, `NaimenovanjaExportHandler` i
  `NaimenovanjaValidationHandler`.

### 1c) `gui/tabs/sifarnici_view.py` — 3.654 linije, 89 metoda

- **Opis**: Sadrzi sve sifarnike (tarife, drzave, procedure, dokumente, kvote,
  inspekcije) u istoj klasi.
- **Prijedlog**: Svaki sifarnik bi trebao biti zaseban widget (sto je djelimicno
  zapoceto sa `tariff_hierarchy.py`, `quota_panel.py`).

### 1d) `services/zaglavlje_service.py` — 1.947 linija, najveci servis

- **Opis**: Pet funkcija cini 1.351 liniju od 1.947: `load_from_draft()` (270),
  `save_to_draft()` (223), `_parse_xml()` (251), `parse_naimenovanja_from_xml()` (324),
  `validate()` (283).
- **Prijedlog**: Podijeliti na `ZaglavljeLoadService`, `ZaglavljeSaveService`,
  `ZaglavljeXmlParser`, `ZaglavljeValidator`.

---

## 2. `print()` sa emoji na Windows — MEDIUM

AGENTS.md i §43 dokumentuju da emoji na stderr (cp1252) uzrokuje pad na Windows.
I pored toga, **5 produkcionih fajlova** i dalje koristi `print()` sa emoji.

| Fajl | Linija | Kod |
|------|--------|-----|
| `gui/dialogs/enhanced_tariff_suggestion_dialog.py` | 752, 754 | `print(f"Odabran...")` / `print("Dijalog...")` |
| `gui/dialogs/enhanced_validation_dialog.py` | 838, 840 | `print(f"Dijalog...")` / `print("Dijalog...")` |
| `gui/tabs/agent_tab.py` | 57, 59, 66 | `print(f"[AgentTab] ...")` / `print(f"...")` |
| `services/carinski_dokumenti_service.py` | 76 | `print(f"Greska...")` |
| `services/knowledge_base/kb_service.py` | 133, 167 | `print(f"  Greska...")` |

- **Posljedice**: Aplikacija puca na Windows cp1252 konzoli ako se pokrene iz
  terminala. U PyInstaller .exe build-u nije problem (nema konzole), ali to nije
  uvijek slucaj (debug mod, `--console` build).
- **Prijedlog**: Zamijeniti sa `logger.warning()` / `logger.info()`.

---

## 3. `from ... import *` bez `__all__` — LOW

`gui/tabs/agent/constants.py` (72 linije) nema `__all__` definiciju, ali ga
**7 fajlova** importuje sa `from ... constants import *`:

- `agent_view.py`, `chat_panel.py`, `document_panel.py`, `file_table.py`,
  `header_bar.py`, `results_viewer.py`, `upload_area.py`

- **Posljedice**: Ako bilo koji od ovih fajlova definise varijablu sa istim imenom
  kao u `constants.py`, dobija se neocekivano ponasanje (tiha shadowing).
- **Prijedlog**: Dodati `__all__` u `constants.py` sa eksplicitnom listom imena.

---

## 4. Re-export shimovi — MEDIUM

**27 fajlova** su cisti re-export shimovi: jedna linija `from ... import *` sa
`# noqa: F401, F403`.

**13 u `services/agent/`**: `chat_memory_service.py`, `declaration_search_service.py`,
`declaration_validator_service.py`, `enhanced_tariff_suggestion_service.py`,
`exporter_xml_indexer.py`, `historical_learning_service_safe.py`,
`hybrid_tariff_agent.py`, `intent_classifier.py`, `merge_intent_service.py`,
`naimenovanja_intent_service.py`, `naimenovanja_review_service.py`,
`supplier_profiling_service.py`, `tariff_intent_service.py`

**14 u `importers/`**: `blagic_attos_importer.py`, `blagic_combined_importer.py`,
`blagic_importer.py`, `blagic_loren_importer.py`, `blagic_loren_pdf_parser.py`,
`imamoglu_excel_importer.py`, `imamoglu_pdf_parser.py`,
`leburic_pekabesko_importer.py`, `master_frigo_importer.py`,
`medicopharm_importer.py`, `pip_food_parser.py`, `sumaprom_combined_importer.py`,
`sumaprom_excel_parser.py`, `sumaprom_pdf_parser.py`

- **Posljedice**: Otezavaju navigaciju (IDE prikazuje dvije verzije istog koda),
  povecavaju broj fajlova za 27, i maskiraju stvarne import greske (zato imaju
  `# noqa`).
- **Prijedlog**: Ako niko vise ne importuje sa starih putanja, obrisati shimove
  i preseliti sve importe na nove putanje.

---

## 5. DB_PATH ponavljanje — MEDIUM

Obrazac `_resolve_db_path` sa `__file__`-relativnom putanjom se ponavlja na
**8 mjesta**. Neka su popravljena u §44/45, ali **2 su ostala nepopravljena**:

| Fajl | Status | Rizik |
|------|--------|-------|
| `services/tariff_doc_history_service.py:56` | Bez frozen fallback-a | **Puca u .exe build-u** |
| `services/agent/llm_audit_log.py:24` | Bez frozen fallback-a | **Puca u .exe build-u** |

- **Posljedice**: `tariff_doc_history_service` koristi `tariff_doc` tabelu
  (historijski tarifni prijedlozi). `llm_audit_log` vodi evidenciju LLM tokena.
  U .exe build-u bi konekcija otisla na pogresnu putanju i napravila praznu bazu.
- **Prijedlog**: Primijeniti isti `_resolve_db_path()` obrazac (lista kandidata
  + frozen fallback na exe folder) kao u ostalim popravljenim fajlovima.

---

## 6. Veoma velike funkcije (>200 linija) — LOW

AST analiza je otkrila **10 funkcija** duzih od 200 linija:

| Linija | Fajl | Funkcija |
|--------|------|----------|
| 335 | `gui/tabs/agent/services/chat_intent_handler.py:1364` | `_handle_message_regex_fallback` |
| 331 | `gui/tabs/zaglavlje_view.py:1975` | `_apply_styles` |
| 324 | `services/zaglavlje_service.py:1206` | `parse_naimenovanja_from_xml` |
| 324 | `gui/tabs/faktura_view.py:3263` | `_on_import_finished` |
| 318 | `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py:342` | `parse_leburic_pekabesko_pdf` |
| 285 | `memory/update_refactoring_complete.py:16` | `add_complete_refactoring_memory` |
| 283 | `services/zaglavlje_service.py:1665` | `validate` |
| 270 | `services/zaglavlje_service.py:424` | `load_from_draft` |
| 270 | `importers/vendors/pip_food/pip_food_parser.py:59` | `parse_pip_food_pdf` |
| 253 | `importers/vendors/imamoglu/imamoglu_pdf_parser.py:21` | `parse_imamoglu_pdf` |

- **Posljedice**: Funkcije >200 linija su tesko testabilne, tesko citljive i
  tesko odrzive.
- **Prijedlog**: Svaku podijeliti na vise manjih, imenovanih helper funkcija.
  Posebno: `_handle_message_regex_fallback` (vise intenta u jednoj funkciji),
  `parse_leburic_pekabesko_pdf` (zaglavlje/stavke/pakovanja/tezine),
  `_on_import_finished` (razliciti tipovi importa).

---

## Dodatno: Uoceni tokom istrage (dopuna)

### `config.ini` ne postoji — AGENTS.md zastario

AGENTS.md navodi: "PostgreSQL 16 (server `dmserver`, IP je DHCP — citati iz
`config.ini`, ne hardkodovati". Medjutim:
- `config.ini` **ne postoji** u repozitorijumu
- Stvarna DB konfiguracija se cita iz `.env` fajla preko `pydantic_settings`
  (`config/settings.py:51-55`)
- `.env` fajl postoji i sadrzi DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
- **Posljedica**: AGENTS.md je nekonzistentan sa stvarnim kodom. Novi agenti
  koji procitaju AGENTS.md ce tražiti nepostojeci `config.ini`.
- **Prijedlog**: Azurirati AGENTS.md da reflektuje stvarno stanje (.env + pydantic).

### `scripts/*.md` — agent reporti u pogresnom folderu

`scripts/` sadrzi **6 markdown fajlova** koji su po sadržaju agent reporti ili
dizajn dokumenti, a ne skripte:
- `docs/archive/2026-04-26/CHANGES_2026-04-26.md`,
  `docs/archive/2026-04-26/dead_code_cleanup_2026-04-26.md`,
  `docs/archive/2026-04-26/master_frigo_agent_import_2026-04-26.md`,
  `docs/archive/2026-04-26/perf_and_stability_2026-04-26.md`,
  `docs/archive/2026-04-26/quota_module_2026-04-26.md`,
  `docs/archive/2026-04-26/rename_asycuda_to_deklarant_2026-04-26.md`
- **Posljedica**: Nekoherentna organizacija — agent reporti su na tri mjesta:
  `agent_reports/`, `docs/`, `scripts/`.
- **Prijedlog**: Premjestiti u `agent_reports/` (ili `docs/`) radi konzistentnosti.

### Zastarjeli backup CSV fajlovi u `scripts/`

`scripts/` sadrzi **8 CSV fajlova** sa backup podacima iz juna 2026:
`_izvoznici_merge_backup_*.csv`, `_izvoznici_move_backup_*.csv`,
`_tariff_mapping_fix_backup_*.csv`, `_uvoznici_fix_backup_*.csv`,
`_uvoznici_move_backup_*.csv`
- **Posljedica**: Nepotrebno povecavaju repo (~200KB+). Backup podaci ne
  bi trebali biti u git repozitorijumu.
- **Prijedlog**: Obrisati (podaci su vjerovatno samo za jednokratnu migraciju).

### `mcp_server/tools/` — moguca duplikacija sa agent tool-ovima

`mcp_server/tools/` sadrzi 5 tool fajlova (`preference.py`, `product_origin.py`,
`tariff_history.py`, `validation.py`, `exporter_template.py`). Istovremeno,
`gui/tabs/agent/` ima sopstveni tool sistem (`tool_definitions.py`,
`tool_dispatcher.py`, `tool_policy.py`).
- **Posljedica**: Dvije paralelne tool definicije — MCP tools (za spoljne AI
  asistente) i agent tools (za ugrađeni chat). Ako se logika razilazi, isti
  koncept (npr. "provjeri tarifu") moze imati drugacije ponasanje.
- **Prijedlog**: Provjeriti da li su MCP tools samo tanak proxy na agent tools
  ili imaju sopstvenu, potencijalno razlicitu, implementaciju.

---

## Dodatno: Uoceni tokom istrage (original)

### `memory/` folder — legacy artefakt

Folder `memory/` sadrzi ~20 fajlova koji su ranija verzija MCP memory sistema.
Vecina ima `memory_mcp_server_universal.py` sa istom logikom u vise kopija.
Neki su u `memory/agent_memory_v1.1.1_STABLE/agent_memory/`. Ovo je vjerovatno
legacy koji se vise ne koristi (zamijenjen sa `docs/CONTEXT.md` i `mcp_server/`).

### `.worktrees/` folder — Codex radna grana

`.worktrees/codex-faktura-toolbar/` sadrzi kompletnu kopiju projekta (Codex-ov
rad na redizajnu faktura taba). Git worktree, ne duplikat. Samo napomena.

---

## Prioritet za buduce akcije

| Prioritet | Sta | Razlog |
|-----------|-----|--------|
| HIGH | `tariff_doc_history_service.py` + `llm_audit_log.py` DB_PATH | Puca u .exe build-u, isti obrazac kao §44 |
| HIGH | 4 prevelike klase/fajla | SRP krsenje, otezano odrzavanje |
| MEDIUM | `print()` sa emoji u 5 fajlova | Pad na Windows cp1252 konzoli |
| MEDIUM | 27 re-export shimova | Nepotreban import indirection sloj |
| MEDIUM | DB_PATH ponavljanje na 8 mjesta | Trebalo bi centralizovati |
| MEDIUM | AGENTS.md navodi `config.ini` koji ne postoji | Nekonzistentna dokumentacija vodi u pogresnom smjeru |
| MEDIUM | `scripts/*.md` — 6 reporta u pogresnom folderu | Nekoherentna organizacija |
| LOW | `from ... import *` bez `__all__` | Tiha shadowing varijabli |
| LOW | 10 funkcija >200 linija | Refaktor preporuka |
| LOW | 8 CSV backup fajlova u `scripts/` | Nepotrebno povecavaju repo |
| LOW | `mcp_server/tools/` moguca duplikacija | Dvije tool definicije, potencijalno razlicite |
