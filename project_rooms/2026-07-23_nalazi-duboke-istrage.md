# Izvjestaj duboke istrage kodne baze — Deklarant Pro

**Datum**: 2026-07-23
**Agent**: Pi (istrazivacki rezim)
**Metodologija**: grep/AST sken → potvrda kroz citanje koda → klasifikacija

---

## Sazetak (broj potvrdjenih nalaza po oblasti)

| # | Oblast | Nalaza | Prioritet |
|---|--------|--------|-----------|
| 1 | `except Exception: pass` u `services/` | 1 ozbiljan + 1 informativan | **HIGH** |
| 2 | Qt threading van LLM poziva | 0 novih (sve pokriveno u §43) | — |
| 3 | Bulk QTableWidget bez `blockSignals` | 3 potvrdjena | **MEDIUM** |
| 4 | f-string u SQL | 0 (AGENTS.md pravilo postovano) | — |
| 5 | `mock` za DB u testovima | 0 (zabrana postovana) | — |
| 6 | Nedostajuci `consumed_paths` | 1 potvrdjen | **HIGH** |
| 7 | Preostali dist_client drift | 1 ozbiljan + 4 benigna | **HIGH** |
| 8 | QThread lifecycle / cleanup | 0 aktivnih (ali bezbjedno gasenje nije potpuno) | **LOW** |

---

## Detaljni nalazi

### [1] `except Exception: pass` — tiho gatanje gresaka u servisnom sloju

#### 1a) `evidence_adapters.py` — tiho guta greske pri pretrazi tarifnih mapiranja

- **Fajl:Linija**: `services/decision/evidence_adapters.py:91`
- **Opis**: `_find_tariff_mappings()` helper ima `except Exception: pass` koji guta sve greske pri DB upitu za tarifna mapiranja. Ako baza vrati gresku (konekcija prekinuta, None vrijednost), korisnik dobija **praznu listu kandidata bez ikakvog traga u logu**.
- **Dokaz**: Direktan citat koda:
  ```python
  except Exception:
      pass
  return candidates  # prazna lista, korisnik vidi "nema prijedloga"
  ```
- **Da li je aktivan kod**: DA — `_find_tariff_mappings()` se poziva iz `evaluate_line()` u `decision_service.py`, koji se poziva iz: agent auto-popuna tarifa (`import_pipeline_service`), rucna validacija (`faktura_view`), "Provjeri" dugme.
- **Predlog fixa**: Dodati `logger.exception("Tariff mapping lookup failed")` ili bar `logger.warning` prije `pass`. Isti obrazac kao popravljen `tariff_tree_service.py` iz §45.
- **Procijenjen scope**: Sve funkcionalnosti koje zavise od automatskog prijedloga tarifnih brojeva: agent pipeline, faktura tab validacija, "Provjeri" dugme.

#### 1b) `declaration_search_service.py` — XML helper tiho guta greske

- **Fajl:Linija**: `services/agent/chat/declaration_search_service.py:71`
- **Opis**: `_txt()` helper za XML element parsing ima `except Exception: pass`. Ako XML struktura nije ocekivana, vraca prazan string bez ikakvog traga u logu.
- **Dokaz**:
  ```python
  def _txt(element, path, default=""):
      try:
          el = element.find(path)
          if el is not None and el.text:
              return el.text.strip()
      except Exception:
          pass
      return default
  ```
- **Da li je aktivan kod**: DA — koristi se za parsiranje XML deklaracija u historijskoj pretrazi.
- **Predlog fixa**: Dodati `logger.warning("XML parse failed: %s", path)` prije `pass`.
- **Procijenjen scope**: Agent chat pretraga deklaracija, historijski prijedlozi tarifa.

---

### [3] Bulk QTableWidget operacije bez `blockSignals`

**Zajednicki obrazac**: AGENTS.md (§5) i CONTEXT.md zahtijevaju `blockSignals(True/False)` prije/poslije bulk `setRowCount` + `setItem` petlji. Tri mjesta ne slijede ovaj obrazac.

#### 3a) `sifarnici_view.py` — bulk populate bez `blockSignals`

- **Fajl:Linija**: `gui/tabs/sifarnici_view.py:1298-1310`
- **Opis**: `_populate_table_from_service()` koristi `setUpdatesEnabled(False/True)` (sprjecava vizuelno treperenje) ali **NE `blockSignals`** (ne sprjecava emitovanje signala za svaki red).
- **Dokaz**:
  ```python
  self.table.setSortingEnabled(False)
  self.table.setUpdatesEnabled(False)
  self.table.setRowCount(actual_rows)
  for row in range(actual_rows):
      for col, col_name in enumerate(columns):
          self.table.setItem(row, col, ...)
  self.table.setUpdatesEnabled(True)
  self.table.setSortingEnabled(True)
  # NEMA blockSignals(True/False)
  ```
- **Da li je aktivan kod**: DA — pri svakoj pretrazi u Sifarnici tabu.
- **Predlog fixa**: Dodati `self.table.blockSignals(True)` prije `setRowCount` i `self.table.blockSignals(False)` poslije petlje.
- **Procijenjen scope**: Sifarnici tab pretraga (tarife, drzave, procedure, dokumenti).

#### 3b) `tariff_hierarchy.py` — bulk populate bez blockSignals i setUpdatesEnabled

- **Fajl:Linija**: `gui/tabs/sifarnici/tariff_hierarchy.py:131-164`
- **Opis**: `_populate_tariff_table()` bulk popunjava tabelu tarifne hijerarhije **bez ikakve zastite** — ni `setUpdatesEnabled` ni `blockSignals`.
- **Dokaz**:
  ```python
  table.setRowCount(len(rows_to_show))
  for i, (kod, naziv, ...) in enumerate(rows_to_show):
      table.setItem(i, 0, item_kod)
      table.setItem(i, 1, item_naziv)
  ```
- **Da li je aktivan kod**: DA — pri svakoj pretrazi u tarifnoj hijerarhiji (Sifarnici → Tarifa).
- **Predlog fixa**: Dodati `table.setUpdatesEnabled(False)` + `table.blockSignals(True)` prije petlje, i obrnuto poslije + `viewport().update()`.
- **Procijenjen scope**: Sifarnici → Tarifa hijerarhijski pregled.

#### 3c) `quota_panel.py` — bulk populate bez blockSignals

- **Fajl:Linija**: `gui/tabs/sifarnici/quota_panel.py:280-310`
- **Opis**: `_populate_table()` bulk popunjava tabelu kvota bez `blockSignals`.
- **Dokaz**:
  ```python
  self.table.setRowCount(0)
  self.table.setRowCount(len(rows))
  for r, item in enumerate(rows):
      for c, val in enumerate(values):
          cell = QTableWidgetItem(str(val))
          self.table.setItem(r, c, cell)
  ```
- **Da li je aktivan kod**: DA — pri svakoj pretrazi kvota.
- **Predlog fixa**: Dodati `self.table.blockSignals(True)` prije i `self.table.blockSignals(False)` poslije petlje.
- **Procijenjen scope**: Sifarnici → Kvote panel.

---

### [6] Nedostajuci `consumed_paths` u kombinovanom importeru

#### 6a) `sumaprom_combined_importer.py` — NE postavlja consumed_paths

- **Fajl:Linija**: `importers/vendors/sumaprom/sumaprom_combined_importer.py` (cijeli fajl)
- **Opis**: `combine_sumaprom_excel_and_pdf()` prima Excel i PDF putanje, interno parsira oba fajla i kombinuje podatke, ali **NE postavlja `consumed_paths`** na povratnom `ImportResult`-u. AGENTS.md eksplicitno navodi Sumaprom CASE 1B/2B kao primjer gdje je `consumed_paths` obavezan.
- **Dokaz**: Funkcija vraca `(combined_items, stats)` tuple, ne `ImportResult`. Poredjenje: `blagic_attos_importer` (linija 658) ISPRAVNO postavlja `consumed_paths=[packing_list_path]`, a `blagic_combined_importer` (linija 439) takodje.
- **Da li je aktivan kod**: DA — `sumaprom_combined_importer` je registrovani kombinovani importer, poziva ga `smart_pdf_importer` i/ili `import_pipeline_service`.
- **Predlog fixa**: Refaktorisati povratnu vrijednost da koristi `ImportResult` sa `consumed_paths=[excel_path, pdf_path]` ili bar `consumed_paths=[excel_path]`.
- **Procijenjen scope**: Import pipeline za Sumaprom fakture → **duplikati stavki** (svaka stavka se pojavljuje dva puta u deklaraciji).

---

### [7] Preostali dist_client drift — sistematski pregled

Bajt-po-bajt poredjenje 1.425 uparenih `.py` fajlova root/dist_client: **10 sa stvarnom razlikom** (nakon normalizacije BOM/CRLF/trailing whitespace).

| Fajl | Status |
|------|--------|
| `exporters/asycuda_xml_builder.py` | Namjerno preskocen (poznat, slozen) |
| `importers/packing_list_parser.py` | Samo reordering funkcija (benigno) |
| `services/tariff/tariff_mapping_service.py` | `.pyd` shim (namjerno) |
| `services/tarifa_service.py` | Frozen-build patch (namjerno) |
| `app/run.py` | Frozen-build patch (namjerno) |
| `config/settings.py` | Frozen-build patch (namjerno) |
| `services/draft_autosave_service.py` | Nov fajl (Pi agent) |
| **`gui/tabs/faktura_view.py`** | **STVARAN DRIFT — vidi 7a)** |
| `importers/vendors/sumaprom/sumaprom_excel_parser.py` | Samo BOM + 1 komentar (benigno) |
| `ui/naimenovanja_tab_OPTIMIZED_ui.py` | Qt verzija + geometrija (benigno) |
| `ui/zaglavlje_tab_ui.py` | Qt verzija + 1 string (benigno) |

#### 7a) `faktura_view.py` — stvaran funkcionalan drift

- **Fajl**: `gui/tabs/faktura_view.py` (root 240.990 vs dist_client 240.728 bajtova)
- **Opis**: Root verzija ima **refaktorisan toolbar** sa odvojenim "PDF" i "Pregled" dugmadima, promijenjene boje sekcija, izmijenjenu validacionu paletu boja. Dist_client ima **staru verziju** sa jednim "PDF" dugmetom + QMenu sa dvije opcije ("Spisak naimenovanja", "Pregled po fakturama").
- **Dokaz**: `diff` prikazuje ~260 linija razlike (vidi `diff -u gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py`).
  - Root: dva odvojena dugmeta `btn_export_pdf` i `btn_pregled_faktura`
  - Dist_client: jedno dugme `btn_export_pdf` sa `QMenu` (padajuci meni)
  - Boje sekcija promijenjene iz palete po tipu u uniformnu `#E9EEF3`
  - Validacione boje promijenjene (zuta: `#FFF4D6` → `#fff9c4`, plava: `#E6F0F8` → `#cce5ff`, crvena: `#F9E4E3` → `#ffcccc`)
  - `_create_button` visina i stil izmijenjeni
- **Da li je aktivan kod**: DA — `faktura_view.py` je centralni View za cijelu aplikaciju. Svaki build koristi dist_client verziju.
- **Predlog fixa**: Mirrorati root izmjene u dist_client (obratiti paznju: ovo je Codex-ov redizajn, mozda nije namjera da se prepise — potvrditi sa korisnikom).
- **Procijenjen scope**: Izgled i funkcionalnost Faktura taba u shipped .exe izdanju.

#### 7b) Benigni fajlovi

- `importers/vendors/sumaprom/sumaprom_excel_parser.py`: Samo BOM razlika + 1 komentar (linija 628) dodat u root. Nema funkcionalne razlike.
- `ui/naimenovanja_tab_OPTIMIZED_ui.py`, `ui/zaglavlje_tab_ui.py`: Autogenerated Qt UI fajlovi. Razlike su: Qt verzija u header-u (6.10.2 vs 6.11.1, 6.11.0 vs 6.11.1), pomjeranje geometrije (linija 68-75), i jedna string promjena ("prevoz" → "prijevoz"). **Bez funkcionalnog uticaja** — ovi fajlovi su input za `uic` i ne koriste se direktno u runtime-u.

---

### [8] QThread lifecycle / cleanup

- **Nema aktivnog crash buga**: `MainWindow._confirm_safe_to_exit()` upozorava korisnika ako worker jos radi (linija 181-185). `_worker.finished.connect(self._worker.deleteLater)` osigurava cleanup (linija 303).
- **Bezbjedno gasenje nije potpuno**: Ako korisnik odabere "Yes" na upozorenju ("zelim zatvoriti uprkos radecem workeru"), nema eksplicitnog `_worker.quit()` + `_worker.wait()` prije zatvaranja. Qt ce baciti "QThread: Destroyed while thread is still running" upozorenje (ali ne i crash — Qt automatski handling).
- **Predlog fixa**: Dodati `worker.quit()` i `worker.wait(5000)` u `_on_exit_clicked()` prije `self.close()` ako worker jos radi.

---

## Prioritet za Claude Code (redoslijed popravke)

1. **HIGH** — `evidence_adapters.py:91` (except Exception: pass) — isti obrazac kao bug iz §45 koji je bio slomljen mjesecima
2. **HIGH** — `sumaprom_combined_importer.py` (nedostaje consumed_paths) — dovodi do duplikata stavki
3. **HIGH** — `faktura_view.py` dist_client drift — funkcionalna razlika u shipped build-u (potvrditi da li je namjerno)
4. **MEDIUM** — 3 QTableWidget bulk operacije bez blockSignals (sifarnici_view, tariff_hierarchy, quota_panel)
5. **LOW** — `declaration_search_service.py:71` (XML parse bez logovanja)
6. **LOW** — QThread quit/wait pri zatvaranju ako worker jos aktivan

---

## Sta NIJE potvrdjeno (negativni rezultati, jednako vazni)

- **Threading van LLM**: Jedini slucaj (`system_panel.py`) popravljen u §43. Nema novih nalaza.
- **SQL injection**: Svaki SQL upit koristi parametrizovane `?` vrijednosti. Strukturni dijelovi (WHERE, ORDER BY) koriste interne, kontrolisane stringove. Nulta tolerancija na injection — AGENTS.md pravilo se postuje.
- **mock za DB u testovima**: Testovi koriste `monkeypatch` (pytest) ili prave SQLite fajlove. MagicMock se ne koristi za DB konekcije.
- **Duplicirane metode/funkcije**: Potvrdjeno cisto (iz §45). Nema sistemskog obrasca.
