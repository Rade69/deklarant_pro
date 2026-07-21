# Agent Report — 2026-07-21: Preciznost tarifnih prijedloga (Auto-popuni + Provjeri)

## Datum
2026-07-21

## Agent
Claude Sonnet 5

## Scope
- `services/tariff/tariff_mapping_service.py` (dist_client: samo `.pyd`, vidi "Šta nije urađeno")
- `services/tariff_facade.py` (dist_client: samo `.pyd`, vidi "Šta nije urađeno")
- `gui/tabs/faktura_view.py` + dist_client
- `core/decision/evidence.py` + dist_client
- `gui/tabs/agent/widgets/tariff_validation_dialog.py` + dist_client
- `tests/unit/test_tariff_mapping_service.py` (novo), `test_tariff_validation_dialog.py`
- `project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md`

## Status izvora

- Korisnikov zahtjev proistekao iz dvije uzastopne istrage u ovoj sesiji: (1) analiza
  "Auto-popuni" dugmeta na zahtjev "prijedlog tarifa mora biti maksimalno tačan", (2)
  analiza "Provjeri" dugmeta (`TariffValidationDialog`) na isti zahtjev, korisnik potom
  eksplicitno tražio "uključi sve zajedno" — obje istrage spojene u jedan plan.
- `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md` (Codex) — aktivan,
  §6.2/§6.3 su nezavisno identifikovali sličan problem (N+1 upiti, nekontrolisano
  auto-učenje) na širem nivou; ovaj zadatak je uži i fokusiran na dva konkretna GUI toka.

## GitNexus impact

Prije izmjene: `TariffFacade` MEDIUM (30), `TariffMappingService` MEDIUM (82, class-level
fan-in — stvarno dirane metode uže), `core/decision/evidence.py::build_evidence` **CRITICAL**
(44 pozivaoca, dijeli origin/preference/document evidence) — **NIJE DIRAN**,
`evidence_from_tariff_decision` LOW (graf pokazuje 0, potvrđeno čitanjem: tačno 1 stvaran
pozivalac).

Nakon svih commitova: `gitnexus_detect_changes(scope="all")` → **risk_level: HIGH**,
80 promijenjenih simbola, 11 fajlova, 12 affected_processes — svi kroz `find_mapping`/
`auto_populate_tariffs` (očekivano, to su tačno funkcije koje su namjerno mijenjane).
Pozivaoci koji `find_mapping()` već zovu sa eksplicitnim `min_similarity=0.92`
(`services/decision/evidence_adapters.py:57`) nisu pogođeni promjenom DEFAULT vrijednosti.
`build_evidence` se ne pojavljuje u affected_processes — potvrđuje da CRITICAL simbol
nije dotaknut.

## Šta je urađeno

### Fix Set A — Auto-popuni (Faktura toolbar)

1. **`TariffMappingService.auto_populate_tariffs()`** — dodat `dry_run: bool = False`.
   Logika razdvojena u `_compute_line_mapping()` (računanje: istorija dobavljača →
   `find_mapping`, BEZ upisa) i `_apply_mapping_to_line()` (upis) — obje grane
   (`auto_populate_tariffs` i novi `commit_proposals`) dijele ISTI proračun, jedan izvor
   istine. Novi `TariffProposal` dataclass nosi `line_no/tarifni_broj/source/confidence`
   + sam `mapping` objekat.
2. **`commit_proposals()`** (novo) — upisuje prethodno izračunate `proposals` BEZ ponovnog
   pozivanja `find_mapping()`/istorije — dokazano testom da čak i kad bi `find_mapping()`
   u međuvremenu vratio DRUGAČIJI rezultat, `commit_proposals` upisuje baš ono što je bilo
   u preview-u.
3. **`min_similarity` default 0.70 → 0.92** (projektni kanon, AGENTS.md) — korisnik
   eksplicitno potvrdio ovaj tradeoff (manje automatskih pogodaka, manje lažnih pozitiva)
   preko `AskUserQuestion`.
4. **`TariffFacade`** — `auto_populate_tariffs` već prosljeđivao `**kwargs` (dry_run
   automatski protekao), dodat `commit_proposals()` passthrough.
5. **`faktura_view._collect_tariff_previews`** — poziva `facade.auto_populate_tariffs(
   dry_run=True)` umjesto `suggest_fast()` (koji nije uzimao dobavljača ni istoriju XML
   deklaracija u obzir — to je bio GLAVNI bug: dijalog i upis su bila dva nezavisna
   proračuna koja su se mogla razići).
6. **`faktura_view._on_auto_fill`** — nakon potvrde poziva `facade.commit_proposals()`
   sa keširanim `preview_result.proposals`, ne računa ponovo.
7. **Dijalog za potvrdu** — nova kolona "Izvor / Pouzdanost" (npr. "Istorija dobavljača
   (85%)") — `confidence`/`source` su ranije bili izračunati ali odbačeni prije UI-ja.

### Fix Set B — Istorijska validacija ("Provjeri" dugme)

8. **`match.decision_score` prikazan u dijalogu** umjesto `evidence.score`. Otkriven bug:
   `evidence_from_tariff_decision()` NIKAD nije prosljeđivao stvarni `TariffDecision.score`
   u `build_evidence()` — svaki "slab" prijedlog je pokazivao FIKSNU konstantu 60%
   (`_DEFAULT_SCORES[WEAK_GUESS]`), bez obzira na stvarnu jačinu dokaza (koja realno
   varira, npr. 30-70 unutar iste kategorije).
9. **Probano i ODBAČENO**: prosljeđivanje `decision.score` kroz `evidence_from_tariff_decision`
   → `build_evidence(score=...)`. Razlog: `evidence_score_category()` ima pragove
   95/85/70/50 — stvaran score ispod 50 (čest za SHOW_WEAK) bi prebacio prijedlog u
   `HIDDEN` kategoriju (CRVENA boja), iako je prijedlog AKTIVNO prikazan (show_weak ≠
   suppress) — pogrešan vizuelni signal. Umjesto toga: `evidence.score`/`score_category`
   (boja bedža) ostaju NETAKNUTI (bucket-based, stabilno), a **prikazan broj** dolazi iz
   `match.decision_score` (već izračunat u `HistoricalTariffSearchService._is_actionable_match`,
   samo nikad prikazan) — sigurnija, uža izmjena, `build_evidence()` ostaje potpuno
   netaknut.
10. **"Podudarnost" → "Učestalost korištenja"** — čisto label fix. Ta vrijednost
    (`match.confidence`) mjeri koliko puta je par korišten (`0.60 + usage*0.003 + 0.05`),
    NE tekstualnu sličnost naziva — stari naziv je bio zavaravajuć.

## Zašto je urađeno

Korisnik je uvezao stvarne, kompleksne fakture (94 naimenovanja) i izrazio nesigurnost
u tačnost automatskih tarifnih prijedloga — s pravom, jer je istraga otkrila da (a) ono
što se prikazuje u dijalogu nije nužno ono što se upiše, i (b) brojevi pouzdanosti u
oba dijaloga ne mjere ono što tvrde da mjere. Za proizvod koji direktno utiče na carinski
dug, ovo je P0/P1 nivo nalaz — obrađeno je odmah, uz punu GitNexus proceduru jer je
`build_evidence()` (CRITICAL) bio na dohvat ruke.

## Kako je urađeno

Minimalno-invazivan pristup: `_compute_line_mapping`/`_apply_mapping_to_line` su
EKSTRAHOVANI iz postojećeg `auto_populate_tariffs` tijela bez promjene njegove interne
logike (isti redoslijed: istorija → baza znanja → primjena) — samo razdvojeni na
"računaj" i "primijeni" korake da bi `commit_proposals` mogao ponovo iskoristiti "primijeni"
bez "računaj". Za Fix Set B, kad je prvi pokušaj (proslijediti score u `build_evidence`)
otkrio rizik regresije (crveni bedž na prikazanoj stavci), odmah je revertovan u korist
uže, sigurnije izmjene na nivou prikaza.

## Šta nije urađeno (i zašto — VAŽNO za distribuciju)

- **`build_evidence()` sam** — namjerno netaknut (CRITICAL, 44 pozivaoca dijele isti
  bucket-based default mehanizam za origin/preference/document evidence).
- **`decide_tariff_match()` prag za prikazivanje "slab" prijedloga** (trenutno
  `usage_count >= 2`) — korisnik eksplicitno odlučio da ostane netaknuto u ovom prolazu
  (`AskUserQuestion`), dok se prvo ne vidi efekat ovog fix-a u praksi.
- **`dist_client/services/tariff/tariff_mapping_service.py` i
  `dist_client/services/tariff_facade.py` NISU ažurirani** — otkriveno tokom mirroringa
  da dist_client za OVA DVA modula nema plain `.py` fajl, nego kompajlirani
  `.pyd` (`tariff_mapping_service.cp314-win_amd64.pyd`, `tariff_facade.cp314-win_amd64.pyd`,
  plus širi `tariff.cp314-win_amd64.pyd` paket-nivo kompajlat). Tekstualni mirror je
  fizički nemoguć bez Nuitka rekompilacije, koju ova sesija nema uspostavljenu/verifikovanu.
  **Ovo NE utiče na `.exe` rebuild od ranije u sesiji** — `deklarant_pro.spec` builda
  direktno iz root `.py` source-a (`ROOT = Path(SPECPATH)`, PyInstaller Analysis), ne iz
  `dist_client`-a, pa rebuildovani `dist/DeklarantPro.exe` VEĆ sadrži ovaj fix. Utiče SAMO
  na interaktivno pokretanje `dist_client` venv-a (`start_debug.bat` i sl.) — taj put će
  za ova dva modula i dalje koristiti STARO (pre-fix) ponašanje dok se `.pyd` ne
  rekompajlira ili dok se `dist_client` potpuno ne napusti kao dev-run putanja (već
  najavljeno kao smjer nakon ranije `.exe` vs `dist_client` odluke u ovoj sesiji).
- `HybridMatchingService.find_hybrid_mapping()` interna logika — netaknuta, već
  najjači signal u lancu.
- Već izvezene/odobrene XML deklaracije — fix utiče samo na buduće pozive.

## Verifikacija

```
python -m pytest tests/unit/test_tariff_mapping_service.py -v → 6 passed (novi)
python -m pytest tests/unit/test_tariff_validation_dialog.py tests/unit/test_decision_tariff_policy.py
  tests/unit/test_evidence_model.py -v → 57 passed
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 826 passed, 58 skipped, 3 failed, 1 error (sve 3+1 pretpostojeće/nepovezano —
  vidi "Pronađeni problemi")

python -m py_compile <svi izmijenjeni fajlovi, root+dist_client gdje postoji> → OK
diff (bez BOM) root/dist_client za 3 fajla koja imaju .py par → IDENTIČNI

mcp__gitnexus__detect_changes(scope="all") nakon svih commitova
→ risk_level: HIGH (očekivano, fan-out kroz find_mapping/auto_populate_tariffs),
  build_evidence NIJE u affected_processes (potvrđuje CRITICAL simbol netaknut)
```

## Pronađeni problemi

- 3 test faila + 1 error u punom run-u, sve nepovezane sa ovom izmjenom:
  - `test_no_tabula_import_in_code` — NOVI fail, uzrokovan time što raniji PyInstaller
    rebuild ove sesije stvorio `dist/DeklarantPro/_internal/torch/...` folder koji test
    (skenira cio repo za "tabula" import) sad hvata kao lažni pozitiv. Test-infra
    fragilnost (ne isključuje build output foldere), nepovezano sa tarifnim fix-om.
  - `test_tabula_not_in_smart_pdf` — pre-postojeći cp1252 encoding problem (dokumentovano
    ranije u sesiji).
  - `test_xml_parser_fix.py::test_xml_parser` — pre-postojeća hardkodovana Linux putanja.
  - `test_model_benchmark.py::test_model` — pre-postojeći nedostajući pytest fixture.
- Otkriven `dist_client` `.pyd`/`.py` sloj kompleksniji nego što je ranija sesijska
  analiza pretpostavljala — pored `tariff_mapping_service`/`tariff_facade`, i
  `core/licensing`, `core/validation`, `services/declaration_assembly`, `services/export_service`,
  `services/faktura`, `services/licensing`, `services/tariff_controls_service`,
  `services/tariff_doc_history_service`, `services/tariff_tree_service`, `services/validation`
  su TAKOĐE kompajlirani `.pyd` moduli u dist_client — bilo koja buduća izmjena u tim
  fajlovima će imati isti mirror-blocking problem. Preporuka: follow-up zadatak da se
  ili (a) uspostavi i dokumentuje Nuitka rebuild procedura za ove module, ili (b) potpuno
  napusti dist_client kao izvršni put (već najavljen smjer) i ti moduli se brišu/ignore-uju.

## Konflikti / kontradiktorni izvori

Nema. Plan (project_rooms) je bio jasan, jedina promjena u odnosu na plan je Fix Set B
tačka #9 (probano pa odbačeno rješenje) — dokumentovano gore, sigurnija alternativa
implementirana umjesto originalnog prijedloga.

## Commitovi

| Hash | Poruka |
|------|--------|
| `03c4f74` | fix(tariff): dry_run + commit_proposals, prag 0.70 -> 0.92 u Auto-popuni |
| `f21d31e` | fix(faktura): preview i upis Auto-popuni koriste isti proracun |
| `f8a59e0` | fix(tariff): prikazi stvaran decision_score i preimenuj "Podudarnost" |
| `d604777` | test(tariff): pokrij dry_run/commit_proposals i stvaran decision_score |

## Rizici / ograničenja

- **dist_client interaktivni put (venv) NE sadrži ovaj fix** za `tariff_mapping_service`/
  `tariff_facade` (vidi "Šta nije urađeno") — samo rebuildovani `.exe` ga sadrži. Ako
  korisnik/kolege testiraju preko `start_debug.bat` umjesto `.exe`, vidjeće STARO
  ponašanje (0.70 prag, preview/upis mismatch) za Auto-popuni specifično.
- Podizanje praga na 0.92 znači da će VIŠE stavki ostati bez automatskog prijedloga
  (očekivan, eksplicitno prihvaćen tradeoff) — treba pratiti u praksi da li je omjer
  prihvatljiv.
- "Slab" prag za prikazivanje istorijskih prijedloga (usage_count >= 2) nije dirat —
  i dalje relativno nizak bar, ostavljeno namjerno za sljedeći prolaz nakon što se
  vidi efekat ovog fix-a.

## Potreban follow-up

- Ručno testiranje na `.exe`-u (ne dist_client venv-u): Auto-popuni na realnoj fakturi,
  provjeriti da tarifa u dijalogu == tarifa upisana nakon potvrde.
- Odluka o dist_client `.pyd` modulima (rekompajlirati ili napustiti dev-run put).
- Ako se pokaže da je 0.92 previše strogo u praksi (previše stavki bez prijedloga),
  razmotriti međuvrijednost — korisnik je već svjestan ovog tradeoff-a.
- Razmotriti pooštravanje "slab" prikaz praga (usage_count) nakon što se vidi praktičan
  efekat decision_score transparentnosti.

## Potrebna korisnička potvrda

- Ručni test na rebuildovanom `.exe`-u: Auto-popuni + Provjeri na stvarnoj fakturi,
  potvrditi da su brojevi u dijalozima sad smisleni (variraju, ne fiksni).
- Da li nastaviti sa follow-up stavkama gore, ili preći na drugi prioritet.
