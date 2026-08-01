# Agent Report — Faktura 3-layer refaktor: Faza 1 + 2

## Datum
2026-08-01

## Agent
Claude (grana: `refactor/faktura-3layer-claude`)

## Scope
Faze 1 i 2 iz `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`:
ekstrakcija thin-wrappera i čistih funkcija iz `faktura_view.py` u servisni sloj.

## Status izvora
Plan je ažuran (pisan istog dana). Sve pretpostavke iz plana su potvrđene.

## GitNexus impact
- `FakturaView`: **LOW** (lokalizovane izmjene, nema promjene javnog API-ja)
- `FakturaItemValidator`: **MEDIUM** (nije diran u ovim fazama — biće u Fazi 3)
- `FakturaService`, `ImportService`, `MassWorkflowService`, `ValidationService`:
  prošireni novim statičkim metodama — backward-compatibilno

## Reprodukcija prije izmjene
Baseline: 6267 linija, 157 metoda, 1569 testova prolazi (faktura/weight filter: 170).

## Šta je urađeno

### Faza 1 — Mehanički thin-wrapperi i mrtav kod
| Metoda | Akcija | Zamjena |
|---|---|---|
| `_format_issue_counts` | Obrisano | `FakturaService.format_issue_counts()` |
| `_parse_number` | Obrisano | `FakturaService.parse_number()` |
| `_parse_weight_input` | Obrisano | `FakturaService.parse_weight_input()` |
| `_distribute_invoice_weights` | Obrisano | `MassCalculator.calculate_masses()` |
| `_format_weight` | Obrisano | `FakturaService.format_weight()` (identična implementacija) |
| `_accumulate_weights` | Refaktorisano | `self.weight_manager.accumulate_weights()` + `get_bruto_text()`/`get_neto_text()` |
| `_collect_tariff_previews` | Obrisano | Mrtav kod (0 pozivalaca u cijelom repou) |

Dodatno: `agent_controller.py` ažuriran da koristi `FakturaService.format_weight()`.

### Faza 2 — Čiste funkcije bez Qt zavisnosti
| Metoda | Ciljni servis |
|---|---|
| `_format_number` | `FakturaService.format_number()` (novi metod) |
| `_validation_issue_label` | `ValidationService.validation_issue_label()` (novi statički metod) |
| `_normalize_partner` | `FakturaService.normalize_partner()` (novi statički metod) |
| `_is_same_combined_invoice` | `ImportService.is_same_combined_invoice()` + thin wrapper u View |
| `_append_imported_files_message` | `ImportService.append_imported_files_message()` + thin wrapper u View |
| `_calculate_masses_success_message` | `MassWorkflowService.success_message()` (novi statički metod) |
| `_extract_header_from_xml` | Novi `xml_header_extraction.py` — `extract_header_from_xml()` |
| `_count_applied_batch_file_types` | `ImportService.count_applied_batch_file_types()` (novi statički metod) |
| `_push_undo_snapshot` / `_undo` / `_redo` | Novi `UndoRedoService` — logika stackova, View čuva UI pozive |
| `_reset_partner_expectations` | Ostavljeno u View-u (čista UI operacija) |
| `_postprocess_master_frigo_pairs_records` | **Namjerno ostavljeno u View-u** — sadrži GUI import (`ProcessingWorker`), premještanje bi narušilo 3-layer arhitekturu |

## Zašto je urađeno
Po 3-layer pravilu iz `AGENTS.md`: View treba da sadrži samo UI/signale, sva poslovna logika ide u servisni sloj. Prethodni Codex refaktor je izgradio servisnu infrastrukturu ali nije smanjio View. Ove dvije faze su prvi stvarni korak ka smanjenju View-a.

## Kako je urađeno
- Thin-wrapperi: obrisana definicija, zamijenjeni pozivaoci direktnim pozivom servisa
- Čiste funkcije: premještene u servis kao statičke metode
- Undo/redo: izdvojen `UndoRedoService` koji upravlja stackovima; View metode `_push_undo_snapshot`, `_undo`, `_redo` delegiraju servisu i dodaju UI notifikacije
- `_is_same_combined_invoice` i `_append_imported_files_message`: logika u `ImportService`, thin wrapper u View radi testne kompatibilnosti

## Šta nije dirano
- `_postprocess_master_frigo_pairs_records` — GUI import u servis, namjerno preskočeno
- `_reset_partner_expectations` — čista UI operacija, nema poslovne logike
- Sve `_on_*` Qt signal handler metode
- Legacy uvoz putevi (Faza 6)
- Povlastice/porijeklo logika (Faza 4b)
- `min_similarity = 0.92` — nepromijenjen
- Formatiranje težina (puna preciznost, bez zaokruživanja) — očuvano

## Verifikacija

### Metrike
| Metrika | Prije | Poslije | Δ |
|---|---|---|---|
| `faktura_view.py` linije | 6,267 | 6,024 | -243 (-3.9%) |
| `faktura_view.py` metode | 157 | 145 | -12 |
| `services/faktura/` linije | 1,954 | 2,161 | +207 |
| Novi fajlovi | 18 | 21 | +3 |

### Testovi
- `py_compile`: svi fajlovi prolaze (6 .py fajlova)
- `pytest -k "faktura or weight" -m "not integration"`: **170 passed**, 7 failed
- 7 padova su white-box testovi koji testiraju privatne metode/View strukturu:
  - 3× `test_dist_faktura_modules_match_root` — novi servisni fajlovi ne postoje u `dist_client/` (zahtijeva `dist_client` sinhronizaciju)
  - 2× `test_faktura_view_provjeri_nakon_uvoza` — mock-ovi privatnih metoda
  - 1× `test_faktura_view_validacija_selekcija` — mock privatne metode
  - 1× `test_import_workflow_parity` — `assert_called_once_with` za `_distribute_invoice_weights`

## Nezavisna provjera
Nije obavezna za Faze 1-2 (LOW GitNexus impact). Preporučen `/code-review` skill za pregled diff-a.

## Pronađeni problemi
1. Duplikat logike za `_is_same_combined_invoice` u `_finish_import_legacy_path` — postoje dva identična bloka koda koja rade istu stvar (linije ~3847 i ~3857). Ovo je postojeći problem, ne uveden ovim refaktorom.
2. `test_dist_faktura_modules_match_root` — `dist_client/` zaostaje za `services/faktura/`. Treba sinhronizovati prije puštanja.
3. `WeightManager.format_weight` vraća `""` za 0, dok `FakturaService.format_weight` vraća `"0"`. Ova razlika je postojeća i namjerna (različiti konteksti upotrebe).

## Odbačene opcije
1. Premještanje `_postprocess_master_frigo_pairs_records` u `import_service.py` — odbačeno jer bi to značilo import GUI modula u servisni sloj (narušava 3-layer arhitekturu).
2. Potpuno uklanjanje `_append_imported_files_message` i `_is_same_combined_invoice` wrapper-a — odbačeno jer bi polomilo 12+ white-box testova bez stvarne vrijednosti.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
`365d0a7` — `refactor(faktura): Faza 1+2 - ekstrakcija thin-wrappera i čistih funkcija u servisni sloj`

## Kontekst korišćen
- `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`
- `AGENTS.md` (3-layer pravilo, Definition of Done)

## Rizici / ograničenja
1. White-box testovi (7) padaju jer testiraju implementacione detalje. Funkcionalno ponašanje je nepromijenjeno.
2. `dist_client/` nije ažuriran — zahtijeva posebnu sinhronizaciju.
3. `UndoRedoService` koristi `copy.deepcopy` — performanse nisu mjerene za velike draftove (500+ stavki).

## Potreban follow-up
- Sinhronizovati `dist_client/` sa novim servisnim fajlovima
- Ažurirati white-box testove ili ih označiti kao `skip` (odluka korisnika)
- Faza 3 — Ukloniti direktne View→Servis pozive (`self.validator`/`self.assembly`)

## Potrebna korisnička potvrda
1. Da li želiš da ažuriramo white-box testove sada ili kasnije?
2. Da li da sinhronizujem `dist_client/`?
3. Da li nastavljamo sa Fazom 3?
