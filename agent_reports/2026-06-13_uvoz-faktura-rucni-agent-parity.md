# Uvoz faktura: ručni i agentski uvoz — 3 konkretna fixa za parity

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py`
  (`_import_multiple_files`, `_process_batch_records`,
  `_postprocess_master_frigo_pairs_records` — nova metoda, `_on_import_finished`)
- `gui/tabs/agent/models/file_item.py` + `dist_client/.../file_item.py`
  (`FileItem` — 3 nova polja)
- `gui/tabs/agent/widgets/processing_worker.py` + `dist_client/.../processing_worker.py`
  (`ProcessingWorker.run`)
- `gui/tabs/agent/agent_controller.py` + `dist_client/.../agent_controller.py`
  (`AgentController._on_all_completed`)

## GitNexus impact
Prije izmjene (gathered tokom analize):
- `_apply_import_result_to_header` — risk **LOW**, impactedCount 2
- `ManualBatchImportWorker` — risk **LOW**, impactedCount 7
- `FileItem` (novi polja, additive dataclass) — risk **MEDIUM**, impactedCount 18
  (additive-safe — postojeći konstruktori/pozivi `FileItem(...)` koriste
  keyword/positional argumente bez novih polja, default vrijednosti pokrivaju
  ostatak)
- `AgentController._on_all_completed` — risk **LOW**, impactedCount 0

Nakon izmjene, `gitnexus_detect_changes(scope="staged")` na finalnih 8 fajlova:
`risk_level: "critical"`, 45 promijenjenih simbola, 18 affected, 18 affected
processes. Kritičan rizik dolazi GOTOVO ISKLJUČIVO od `ProcessingWorker.run`
— ta metoda učestvuje u ~15 "Run → X" cross/intra-community procesa
(centralni per-fajl processing loop, vrlo visoka povezanost u grafu). Stvarna
izmjena u `run()` su 3 čiste `getattr(result, "exporter"/"importer"/"currency", ...)`
linije bez uticaja na control flow — "critical" je posljedica POVEZANOSTI
simbola u grafu, ne stvarnog rizika ove konkretne izmjene.

## Šta je urađeno
Implementirana 3 konkretna fixa (iz korisnikovog zahtjeva da ručni i agentski
uvoz faktura budu identični), u `gui/` i `dist_client/` (8 fajlova, +160
linija, čisto aditivno, 0 brisanja):

1. **Fix 1 — Mapping Excel skip u grupnom ručnom uvozu**
   `_import_multiple_files` sada filtrira fajlove koje `ProcessingWorker._is_mapping_xlsx`
   prepoznaje (markeri: tarife/podela/porekla/poreklu/poreklo/porijekla/porijeklu/ptp/15467)
   AKO je takav Excel u istom folderu kao PDF fakture u tom batch-u — identično
   ponašanje kao agent uvoz.

2. **Fix 2 — Master Frigo PDF+Excel finansijsko sparivanje u grupnom ručnom uvozu**
   Nova metoda `_postprocess_master_frigo_pairs_records(records)` u `FakturaView`,
   poziva se na početku `_process_batch_records`. Za PDF stavke detektovane kao
   `master_frigo` (`_detected_format`), traži se pripadajući Excel po
   `ProcessingWorker._normalized_invoice_token`, prepisuju se finansije
   (cijena/iznos/kolicina) preko `ProcessingWorker._apply_excel_financials`, a
   Excel record se markira `skipped=True` (ne ulazi kao posebna faktura).

3. **Fix 3 — Header auto-fill (izvoznik/uvoznik/valuta) u single-file ručnom i
   agent uvozu**
   `_apply_import_result_to_header()` (postojeća, fill-only-if-empty metoda)
   sada se poziva i u `_on_import_finished` (single-file ručni uvoz, nakon
   `isinstance(result, ImportResult)`) i u `AgentController._on_all_completed`
   per-invoice loop (poziva se na `file_item`). Za agent put dodana su 3 nova
   polja na `FileItem`: `exporter`, `importer`, `currency` — popunjava ih
   `ProcessingWorker.run` iz `ImportResult` (`getattr` sa default vrijednostima).

## Zašto je urađeno
Korisnik: "bitno je da se i ručni i agentski uvoz faktura budu identični tj.
da se isto parsiraju, da imamo iste poruke i dijaloge." Nakon analize razlika
između `ManualBatchImportWorker` (grupni ručni), `ImportWorker` (single-file
ručni) i `ProcessingWorker` (agent), identifikovano je 6+ razlika; korisnik je
eksplicitno odabrao opciju **"Samo konkretni bugovi (preporučeno)"** — fix
SAMO ova 3, uz EKSPLICITNO ISKLJUČENJE unifikacije EUR.1/PE2/PE3 dijaloga
(agent = po-faktura dijalog, batch ručni = jedan zajednički dijalog — to je
namjerna arhitektonska razlika, ne bug, i ostaje takva).

## Kako je urađeno
- **Fix 1**: filter dodat u `gui→gui` fajl (`faktura_view.py`), NE u
  `services/import_worker.py`, da se izbjegne services→gui import
  (`ProcessingWorker` živi u `gui/tabs/agent/widgets/`). Konzistentno sa
  postojećim `_pair_sort_key` importom u istom fajlu.
- **Fix 2**: nova metoda radi sa `list[dict]` records (format koji koristi
  batch ručni uvoz: `{"filepath", "items", "skipped", "_import_result", ...}`),
  NE sa `FileItem` (agent format) — reuse SAMO čistih static/classmethod
  helpera iz `ProcessingWorker` ("Block A": `_normalized_invoice_token`,
  `_apply_excel_financials`), bez potrebe za FileItem konverzijom.
- **Fix 3**: `FileItem` dobio 3 nova `Optional`/`str` polja sa default
  vrijednostima (additive, backward-compatible); `ProcessingWorker.run`
  ih popunjava odmah pored postojećeg `consumed_paths` punjenja;
  `AgentController._on_all_completed` poziva
  `fw._apply_import_result_to_header(file_item)` odmah nakon punjenja drafta
  za dijalog (prije `chat.add_activity(...)`).
- Sve izmjene portovane 1:1 u `dist_client/` mirrors (identičan kontekst,
  `dist_client` processing_worker.py već imao potrebne helpere u "Block A").

## Šta nije dirano
- **EUR.1/PE2/PE3 dijalozi** — ostaju namjerno različiti (agent: po-faktura;
  batch ručni: jedan zajednički) — eksplicitna odluka korisnika, van scope-a.
- **DisplayProfile WIP** (drugi, nezavisan posao u toku, ostaje nekomitovan):
  `AGENTS.md`, `CLAUDE.md`, `gui/main_window.py`, `dist_client/gui/main_window.py`,
  `gui/tabs/faktura_view.py` i `dist_client/gui/tabs/faktura_view.py` (hunkovi
  za `apply_display_profile`, `_controls_grid`, `_toolbar_headers`,
  `_toolbar_layouts`, `_weight_labels`, `_weights_widget`, `QSizePolicy` import,
  `btn.setProperty("standardText", ...)`), `gui/utils/display_profile.py`,
  `dist_client/gui/utils/display_profile.py`, `styles/display_profiles.qss`,
  `dist_client/styles/display_profiles.qss`, `tests/unit/test_display_profile.py`,
  `client.log.lck`. Ovi fajlovi su imali pre-existing uncommitted izmjene
  ISPREPLETENE sa mojim editima u istom fajlu (faktura_view.py) — odvojeno
  partial-staging tehnikom (vidi "Pronađeni problemi").
- Poznata, van-scope duplikacija `_normalize_code`/`_has_financials`/
  `_apply_excel_financials`/`_is_master_frigo_pdf_item`/`_postprocess_master_frigo_pairs`
  u `gui/tabs/agent/widgets/processing_worker.py` (Block A vs Block C,
  vidi `2026-06-13_duplicirane-metode-processing-worker.md`) — nije dirana,
  moje izmjene koriste samo Block A.

## Verifikacija
- `python -m py_compile` na svih 8 izmijenjenih fajlova (gui + dist_client) — OK.
- Offscreen test skripta (privremena, obrisana nakon):
  - Fix 1: `ProcessingWorker._is_mapping_xlsx` + pdf_folders filter ispravno
    identifikovao `15467_lista_tarife.xlsx` kao "skip" kad je PDF u istom folderu.
  - Fix 2: `_postprocess_master_frigo_pairs_records` (pozvan kao unbound metod
    na `SimpleNamespace()`) ispravno prepisao `cijena_jed=5.0`/`iznos=50.0` iz
    excel reda u pdf red preko `_apply_excel_financials`, markirao excel
    record `skipped=True`, `items=[]`.
  - Fix 3: `_apply_import_result_to_header` (pozvan kao unbound metod na
    `SimpleNamespace(draft=FakeDraft())`) ispravno popunio
    `izvoznik_naziv`/`izvoznik_adresa`/`primalac_naziv`/`primalac_id`/`valuta`;
    drugi poziv sa drugim exporter/currency NIJE prepisao već-popunjeno polje
    (idempotentnost / fill-only-if-empty potvrđena).

## Pronađeni problemi
- `gui/tabs/faktura_view.py` i `dist_client/.../faktura_view.py` su imali
  pre-existing uncommitted DisplayProfile izmjene u ISTOM fajlu kao moja 3
  fixa (interleaved hunkovi). `git add -p` je interaktivan (zabranjen po
  Bash tool pravilima). Riješeno: `git show HEAD:<file> > tmp.py`, ručno
  primijenjena SAMO moja 3 edita na `tmp.py` (identičan tekst kao u working
  tree), `git hash-object -w tmp.py` + `git update-index --cacheinfo
  100644,<hash>,<file>` — staged blob = HEAD + moja 3 fixa, working tree i
  dalje = HEAD + moja 3 fixa + DisplayProfile WIP (ostaje unstaged).
  Verifikovano `git diff --cached` (samo moje 3 hunka) i `git diff` (samo
  DisplayProfile hunkovi, bez preklapanja).
- `gitnexus_detect_changes(scope="staged")` vratio "critical" — objašnjeno u
  sekciji GitNexus impact (posljedica povezanosti `ProcessingWorker.run`, ne
  stvarnog rizika ovih 3 fixa).

## Commitovi
| Hash | Poruka |
|------|--------|
| `3fae234` | fix(import): uskladi rucni i agentski uvoz faktura (3 konkretna bug-a) |

## Rizici / ograničenja
- `FileItem` je dobio 3 nova polja sa default vrijednostima — additive,
  ne mijenja postojeće pozive, ali `gitnexus_impact` je prijavio MEDIUM/18
  zbog veličine dataclass-a; nije pronađen poziv koji bi bio pogođen.
- Fix 2 (Master Frigo pairing u grupnom ručnom uvozu) NIJE testiran sa
  stvarnim PDF+Excel parom kroz GUI — samo offscreen logika.
- Fix 3 header auto-fill je "fill-only-if-empty" — ako korisnik već ima
  popunjeno zaglavlje (npr. iz prethodne fakture u istom draftu), novo
  zaglavlje se NEĆE prepisati ni za agent ni za single-file ručni uvoz (kao
  i ranije za grupni ručni uvoz — ponašanje je SAD konzistentno, ali vrijedi
  napomenuti ako korisnik očekuje "zadnja faktura uvijek pobjeđuje").

## Potreban follow-up
- Nema poznatog za ova 3 fixa. EUR.1/PE2/PE3 dijalog unifikacija ostaje
  eksplicitno van scope-a (korisnikova odluka).
- DisplayProfile WIP (faktura_view.py + main_window.py + display_profile.py +
  qss + testovi) je odvojen, nezavršen posao — treba ga adresirati u
  posebnoj sesiji/zadatku.

## Potrebna korisnička potvrda
- Grupni ručni uvoz: folder sa PDF fakturama + mapping Excel (npr. naziv sa
  "tarife"/"ptp"/"15467") → provjeriti da se mapping Excel NE prikazuje kao
  posebna faktura.
- Grupni ručni uvoz: Master Frigo PDF + odgovarajući Excel u istom batch-u →
  provjeriti da PDF stavke dobiju cijenu/iznos iz Excel-a i da Excel ne uđe
  kao posebna faktura.
- Single-file ručni uvoz i agent ("Pametna pomoć") uvoz fakture sa praznim
  zaglavljem → provjeriti da se izvoznik/uvoznik/valuta automatski popune iz
  fakture (isto kao što već radi grupni ručni uvoz).
