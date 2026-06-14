# Sync: Faza A — preostale funkcionalne razlike `windows` → `dev`

**Datum:** 2026-06-14
**Grana:** `sync/windows-agent-faza1-8` (bazirana na `dev`)

## Šta je urađeno

Nakon Faza 1-8 (agent chat/tarife/validacija), korisnik je tražio da se
usklade SVI preostali funkcionalni (ne-rendering) dijelovi koda razvijeni u
`windows` grani sa `dev`. Faza A pokriva 6 fajlova:

1. **`services/agent/learning/exporter_xml_indexer.py`** — `RealDictCursor`
   fix: pozicioni `row[0]`/`row[1]` pristup zamijenjen sa `row['ime_kolone']`
   u `find_xml_for_pair`, `find_xml_by_consignee`, `get_all_pairs`, `get_stats`.
2. **`services/zaglavlje_service.py`** — auto-detekcija formata XML-a
   (`AsycudaDocument` root → "pro"), `_r1` field-key fix za izvoznika/primaoca
   u `_parse_pro_xml`, merge PE1/PE2/PE3 brojeva priloženih dokumenata,
   proširena lista obaveznih dokumenata (PZT, N730, N380, DIS, DV1), filter
   legacy kodova (FAK, CMR, SAN, VET, UVK).
3. **`gui/tabs/agent/widgets/processing_worker.py` + `models/file_item.py`** —
   `canonical_path()` dedup za `consumed_files`, novi `FileItem.exporter/
   importer/currency`, `_natural_invoice_parts` zero-pad fix.
4. **`utils/country_normalizer.py`** — `_strip_diacritics()` fallback
   (ŠPANIJA→ES, ŠVAJCARSKA→CH).
5. **`services/validation/validation_service.py`** — ERROR validacija za
   nedostajuću `zemlja_porijekla`.
6. **`importers/xml_importer.py`** — `_trade_name_for_table()` čisti
   trgovački naziv iz `Commercial_Description` (uklanja duplikat tarifnog
   opisa i "Faktura:" liniju).

## Kako je urađeno

- Za svaki fajl: `git diff HEAD origin/windows -- <fajl>` (uz strip BOM-a i
  CRLF preko `sed`, jer windows grana ima UTF-8 BOM + CRLF na svim fajlovima
  pa "sirovi" `git diff` prikazuje cijeli fajl kao izmijenjen).
- Svaki nalaz provjeren u stvarnom kodu (cross-grep pozivača, downstream
  potrošača polja) prije primjene — npr. provjereno da je `FileItem` polje
  zaista nedostajalo i da `_apply_import_result_to_header` zaista zavisi od
  njega.
- Plan objašnjen korisniku PRIJE svake izmjene (po CLAUDE.md procesnom
  pravilu — šta se mijenja i zašto).
- Nakon svih izmjena: `pytest tests/unit` (547 passed, 2 deselected —
  pre-existing failovi nevezani za ovaj rad, potvrđeno na čistom dev-u),
  `tests/test_zaglavlje_service.py` + zaglavlje testovi (16 passed),
  `tests/unit/test_agent_processing_worker_sort.py` (10 passed), import
  sanity check za svih 7 izmijenjenih modula.

## Zašto (odluke i alternative)

- **`processing_worker.py` — Master Frigo pairing NIJE prenešen.** Prvobitni
  diff (108 linija) je izgledao kao da nedostaju metode
  `_normalize_code`/`_apply_excel_financials`/`_postprocess_master_frigo_pairs`
  itd. Provjerom je utvrđeno da `origin/windows` te metode ima **dva puta
  duplicirane** (greška u toj grani) — u dev-u već postoje identične, jednom.
  Stvarni preostali diff je samo `canonical_path`, `FileItem` polja i
  `_natural_invoice_parts`.
- **`FileItem.exporter/importer/currency` — ovo je stvarni bug, ne kozmetika.**
  `agent_controller.py:494` poziva `fw._apply_import_result_to_header(file_item)`
  (feature iz Faza1-8, commit `1d158b2`), a ta funkcija čita
  `getattr(result, 'exporter', None)` itd. Bez ovih polja, `getattr` je uvijek
  vraćao `None` — auto-popuna zaglavlja pri manuelnom uvozu po fajlu nikad
  nije radila. Dodavanje polja čini taj feature funkcionalnim.
- **`_parse_pro_xml` `_r1` fix — stvarni data-loss bug.** `save_to_draft()`
  čita `data['izvoznik_r1']`/`data['primalac_r1']` preko `safe_get`, a
  `_parse_pro_xml` je pisao `_naziv` ključeve → podaci o izvozniku/primaocu su
  se tiho gubili pri uvozu Deklarant Pro XML-a (kombinovano sa load_from_xml
  default "world" parserom koji je pogrešno parsirao Pro XML).
- **`zemlja_porijekla` obavezno polje — ERROR, ne CRITICAL.** Markira red
  crveno u tabeli faktura (vizuelno upozorenje), ne blokira kompletno
  `valid` ako su druga polja OK — usklađeno sa postojećim nivoima
  (`has_blocking_errors()` i dalje tretira ERROR kao blokirajući za
  save/export, što je namjerno: zemlja porijekla je obavezna za Rub.34/36).

## Commitovi

| Hash | Poruka |
|------|--------|
| 78ec04d | fix(agent-learning): RealDictCursor pozicioni pristup vraćao KeyError |
| 176f07a | fix(zaglavlje): popravke pri uvozu XML zaglavlja |
| 754873a | fix(agent-worker): canonical path dedup, FileItem zaglavlje polja i natural sort |
| aa0ea68 | fix(utils): fallback skidanja dijakritika u normalizaciji zemalja |
| 59785ef | feat(validation): zemlja porijekla je obavezno polje stavke fakture |
| 10c6c2c | feat(xml-importer): trgovački naziv iz Commercial_Description bez duplikata |

## Testovi

- `pytest tests/unit` (bez `test_zaglavlje_controller_import_docs.py`,
  deselektovani 2 pre-existing faila): **547 passed**.
- `tests/test_zaglavlje_service.py tests/unit/test_zaglavlje_save_to_draft.py
  tests/unit/test_zaglavlje_validation.py`: 13 passed.
- `tests/unit/test_zaglavlje_controller_import_docs.py` (zasebno, pre-existing
  collection-order issue): 3 passed.
- `tests/unit/test_agent_processing_worker_sort.py`: 10 passed.
- Import sanity check (`QT_QPA_PLATFORM=offscreen python -c "import ..."`) za
  svih 7 izmijenjenih modula: OK.

## Pre-existing failures (NE diraj)

`tests/unit/test_declaration_search_service.py::test_declaration_search_uses_env_paths`
i `::test_declaration_search_requires_meaningful_token_overlap` — padaju i na
čistom `origin/dev`, nevezano za ovaj rad (vidi i prethodni izvještaj Faza 1-8).

## Sljedeći korak

- **Phase B**: `services/tarifa_service.py` (DB path resolution + exception
  handling), `rub31_builder.py` (55-char truncation), male logging cleanup
  izmjene (~15 fajlova: `file_item.py`, `packing_list_parser.py`, ostali).
- **Phase C**: `tariff_mapping_service.py` similarity threshold 0.95→0.98 —
  PAŽLJIVO, u Faza1-8 je NAMJERNO NE prenešeno zbog mixanja sa batch-perf
  reverzijama (vidi `2026-06-14_sync-windows-agent-faza1-8.md`); eventualno
  izvlačenje "neutral country color constant" iz `faktura_view.py`.
- Nakon Phase B/C: finalni `pytest`, memorija, agent report, GitNexus reindex.
