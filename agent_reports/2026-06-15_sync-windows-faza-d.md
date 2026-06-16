# Sync: Faza D — sledeća grupa funkcionalnih razlika `windows` → `dev`

**Datum:** 2026-06-15
**Grana:** `sync/windows-agent-faza1-8` (bazirana na `dev`)

## Šta je urađeno

Nastavak [Faze A](2026-06-14_sync-windows-faza-a.md). Korisnik je tražio
ponovnu provjeru `windows` grane (nove promjene nakon Faze A) i sync u novu
fazu. Analiza je podijelila preostale razlike u Fazu D (7 stavki, core
servisi - niži rizik) i Fazu E (veliki GUI fajlovi sa mix funkcionalno/
rendering - viši rizik, deferred). Faza D pokriva:

1. **`services/agent/validation/declaration_validator_service.py`** —
   `ComplianceCheckService.check()` tolerantan na "naimenovanja-only" radni
   tok (uvoz XML direktno u Naimenovanja, bez ATB stavki fakture); nova
   `validate_declaration_full()` spaja agent-validaciju i
   ComplianceCheckService u jedan `ValidationReport`
   (`compliance_items`, `ValidationCategory.COMPLETENESS`).
2. **`gui/dialogs/enhanced_validation_dialog.py`** — novi tab
   "📄 Kompletnost deklaracije" prikazuje `compliance_items`.
3. **`gui/tabs/zaglavlje_controller.py`** — "Završna provjera" koristi
   `validate_declaration_full`; export XML uklonjen iz auto-flow-a (ostaje
   na zasebnom dugmetu); `_on_import_xml` filtrira zastarjele šifre
   dokumenata (FAK/CMR/SAN/VET/UVK) i za "pro" XML re-import; refaktorisan
   `_merge_import_docs_add_only_missing` sa `_add_doc`/`_merge_number`
   helperima (PE1/2/3 merge brojeva, `_user_entered` marker).
4. **`services/declaration_draft_service.py`** (novi fajl) +
   `tests/unit/test_declaration_draft_service.py` (novi) —
   `DeclarationDraftService.save()/load()` za interni "radni nacrt" XML
   format (`<DeklarantProDraft>`).
5. **`services/zaglavlje_service.py`** — `_parse_pro_xml` popunjava
   `zem_10/zem_11/zem_12/zem_13` (Rb.10-13) i čita `drzava_porijekla` iz
   tačnog elementa (`<Country>`, ne `<General_information>`).
6. **`gui/tabs/agent/services/chat_intent_handler.py`** — popravljena
   putanja importa `ComplianceCheckService` (stari modul ne postoji).
7. **`gui/tabs/admin/panels/learning_panel.py`** — detekcija identičnih XML
   duplikata pri "Dodaj XML" (tiho preskoči ako je hash isti), YesToAll/
   NoToAll za batch prepisivanje, log poruka nakon refresh statistike.

## Kako je urađeno

- Za svaki fajl: `git show origin/windows:<fajl> | sed BOM/CRLF strip` →
  `diff -U10/-U20` protiv trenutnog dev fajla, da se vidi tačan hunk bez
  šuma.
- Svaka izmjena provjerena u kontekstu: `ValidationReport`/`ValidationCategory`
  dataclass struktura, `DeclarationDraft.items`/`invoice_lines` polja,
  postojanje `_file_hash`/`SafeMessageBox.YesToAll`, shim modul
  `services/agent/declaration_validator_service.py` (re-export `*` iz
  `services.agent.validation.declaration_validator_service` - potvrđeno da
  `validate_declaration_full` prolazi kroz `import *`).
- Plan objašnjen korisniku PRIJE svake izmjene.
- Testovi: `pytest tests/unit` (bez `test_zaglavlje_controller_import_docs.py`,
  2 deselected pre-existing) → **551 passed** (+4 nova testa za
  `declaration_draft_service`); `test_zaglavlje_controller_import_docs.py`
  zasebno → 3 passed; `test_pe_rub44_consistency.py` → 7 passed;
  `test_zaglavlje_service.py` + zaglavlje testovi → 13 passed.
  Import sanity check za svih izmijenjenih/novih modula: OK.

## Zašto (odluke i alternative)

- **`ComplianceCheckService.check()` — naimenovanja-only.** Ranije je svaki
  `check()` na praznom `invoice_lines` vraćao samo "Nema uvezenih stavki
  fakture." i prekidao. Sada, ako postoje `draft.items` (naimenovanja) bez
  ATB fakture (npr. re-import gotovog XML-a direktno u Naimenovanja),
  provjere naimenovanja i priloženih dokumenata se i dalje izvršavaju —
  inače bi "Završna provjera" bila beskorisna za taj radni tok.
- **`show_export_button=False` uvijek (umjesto `report.valid`).** Windows
  je eksplicitno odvojio "Završnu provjeru" (čisti pregled stanja) od
  exporta — export XML ostaje na zasebnom dugmetu koje deklarant svjesno
  klikne, čak i kad je deklaracija validna. Sprečava neočekivan auto-export.
- **`_BLOCKED_CODES` filter u controlleru — NIJE duplikat Faza A filtera.**
  Faza A je dodala isti filter samo u `_parse_xml` ("world" parser). Re-import
  Deklarant Pro generisanog XML-a ide kroz `_parse_pro_xml` (root
  `<AsycudaDocument>`), koji filter nema. Controller-level filter na
  `data['attached_documents']` poslije `load_from_xml()` pokriva oba puta —
  defense-in-depth, ne duplikat.
- **`_merge_import_docs_add_only_missing` — PE1/2/3 merge brojeva sa `" | "`.**
  Ranije: duplikat PE koda se jednostavno preskočio (prvi broj se čuva).
  Sada: ako se PE1/2/3 šifra ponovo pojavi (npr. iz draft header docs i iz
  XML uvoza), brojevi se spajaju `" | "`-separatorom umjesto da se izgubi
  drugi broj. `_user_entered: True` marker se dodaje na `existing_docs` ali
  **nije još konzumiran** u dev's `zaglavlje_view.py` (Faza E stavka) —
  trenutno se samo tiho ignoriše preko `.get()`.
- **`DeclarationDraftService` — kreiran, ali NIJE povezan na GUI.** Servis i
  testovi su 1:1 kopija iz windows (156+70 linija), prošli su round-trip
  testove. Dugme "Otvori nacrt" / "Sačuvaj nacrt" u `naimenovanja_view.py`
  je Faza E stavka (deferred) — bez nje servis postoji ali se ne koristi.
  Odluka: dodati ga sada jer je nezavisan i testiran, GUI integracija čeka
  Fazu E.
- **`_on_close`/`close_requested` — NIJE prenešeno.** Windows je uklonio ovu
  vezu jer je "Izlaz" dugme premješteno u `main_window.py` (Exit button +
  display profile, Faza E). Dev's `zaglavlje_view.py` (`btn_izlaz`, linija
  1845) još emituje `close_requested` — uklanjanje veze bi pokvarilo to
  dugme bez zamjene. Ostaje za Fazu E.

## Commitovi

| Hash | Poruka |
|------|--------|
| 6954aef | feat(agent-validation): zavrsna provjera deklaracije (ComplianceCheckService + validate_declaration_full) |
| 791017a | feat(draft): servis za cuvanje/ucitavanje radnih nacrta deklaracije |
| 64596ed | fix(zaglavlje): Rb.10-13 polja i lokacija drzave porijekla pri uvozu Pro XML-a |
| c9b83a0 | feat(admin): detekcija identicnih XML duplikata i 'Primijeni na sve' u Learning panelu |

## Testovi

- `pytest tests/unit` (bez `test_zaglavlje_controller_import_docs.py`,
  2 deselected pre-existing): **551 passed**.
- `tests/unit/test_declaration_draft_service.py`: 4 passed (novi).
- `tests/unit/test_zaglavlje_controller_import_docs.py` (zasebno,
  pre-existing collection-order issue): 3 passed.
- `tests/unit/test_pe_rub44_consistency.py`: 7 passed.
- `tests/test_zaglavlje_service.py tests/unit/test_zaglavlje_save_to_draft.py
  tests/unit/test_zaglavlje_validation.py`: 13 passed.
- Import sanity check za svih izmijenjenih/novih modula: OK.

## Pre-existing failures (NE diraj)

Isti kao u Fazi A — `tests/unit/test_declaration_search_service.py`
(2 testa), nevezano za ovaj rad.

## Sljedeći korak

**Faza E** (deferred, veći GUI fajlovi, mix funkcionalno/rendering):
- `gui/tabs/faktura_view.py` — odvajanje "zemlja porijekla" od "povlastica
  potvrđena" (evidence-based bojenje kolone), "Validacija"→"Provjeri".
- `gui/tabs/naimenovanja_view.py` — otvaranje sačuvanih `.xml` nacrta
  (koristi D2 `DeclarationDraftService`), logger umjesto `sys.stderr`.
  PaintedArrowCombo dio SKIP (dev ima `_ArrowComboBox`/`_ArrowCombo`).
- `gui/tabs/zaglavlje_view.py` — `_user_entered` konzument (za D4 marker),
  dinamičko ažuriranje naziva dokumenta, "Završna provjera" naming. SVG
  strelice SKIP (isti razlog kao gore).
- `gui/main_window.py` — Exit button + display profile sistem (rješava
  `_on_close`/`close_requested` cherry-pick napomenu iz Faze D).
