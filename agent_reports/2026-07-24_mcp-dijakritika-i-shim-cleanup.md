## Datum

2026-07-24

## Agent

Codex

## Scope

- `mcp_server/tools/*` i mirror u `dist_client/mcp_server/tools/*`
- `docs/sections/mcp-*.md` i mirror u `dist_client/docs/sections/`
- interne import putanje u `services/`, `gui/`, `importers/`, `tests/` i `dist_client/`
- uklonjeni stari re-export shimovi u `services/`, `services/agent/`, `importers/` i mirrorima u `dist_client/`
- `docs/CONTEXT.md`

## Status izvora

- `agent_reports/2026-07-23_samostalna-istraga-tehnicki-dug.md` — aktivan kao izvor smjera za tehnički dug.
- `docs/CONTEXT.md` — aktivan; dopunjen novim odlukama.
- GitNexus detect_changes — aktivan; korišten prije commita.

## GitNexus impact

- `search_historical_declarations`, `find_product_origin`, `suggest_tariff_from_history` — prethodno provjereno kao LOW impact za MCP query izmjene.
- `HistoricalLearningServiceSafe` — MEDIUM impact; 8 direktnih importera, bez pogođenih procesa u GitNexus rezultatu. Izmjena je bila samo import-path migracija na `services.agent.learning.*`.
- Finalni `gitnexus_detect_changes(scope=all)` prijavio je CRITICAL zbog širine refactora: 92 fajla, 67 pogođenih tokova. Rizik je strukturni (mnogo import tačaka), ne behavior promjena; ublažen je ciljanim testovima i `py_compile`.

## Šta je urađeno

- MCP historical search sada podržava pretragu bez razlike između osnovnih i dijakritičkih slova (`c/č/ć`, `s/š`, `z/ž`, `d/đ`, `dj/đ`) bez PostgreSQL `unaccent` ekstenzije.
- `search_helpers.py` dobio je `searchable_patterns()` helper koji gradi sigurne regex pattern-e, a MCP alati koriste PostgreSQL `~*`.
- Interni importi su migrirani sa starih top-level shim putanja na stvarne pakete:
  - `services.agent.chat.*`
  - `services.agent.learning.*`
  - `services.agent.validation.*`
  - `services.tariff.*`
  - `services.validation.*`
  - `services.naimenovanja.*`
  - `importers.vendors.*`
- Uklonjeni su stari re-export shim fajlovi koji više nemaju interne pozivaoce.
- Test `tests/test_pdf_plumber_only.py` je sužen da ne skenira PyInstaller `dist/` artefakte i da čita fajlove kao UTF-8.
- `docs/CONTEXT.md` je dopunjen odlukama o MCP dijakritičkoj pretrazi i posebnom `dist_client` `.pyd` mostu.

## Zašto je urađeno

MCP pretraga istorijskih deklaracija je bila osjetljiva na dijakritike, pa unos bez kvačica nije pouzdano nalazio robu upisanu sa kvačicama. Odabrano je rješenje bez `unaccent` ekstenzije jer ne traži dodatne privilegije na PostgreSQL serveru.

Re-export shimovi su ostali nakon ranijeg prestrukturiranja modula. Dok su interni pozivaoci prolazili kroz njih, stvarna arhitektura je bila zamagljena i budući refactori su bili rizičniji.

## Kako je urađeno

- Dodana je regex-normalizacija u `mcp_server/tools/search_helpers.py` i mirror u `dist_client`.
- SQL upiti su ostali parametrizovani; promijenjen je operator sa `ILIKE` na `~*` uz `unnest(%s::text[])`.
- Interne import putanje su migrirane na finalne module, zatim je provjereno da nema preostalih starih putanja.
- Shim fajlovi su uklonjeni tek nakon provjere pozivalaca.
- Specijalni `dist_client/services/tariff/tariff_mapping_service.py` nije uklonjen niti mehanički migriran jer zavisi od `dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd`.

## Šta nije dirano

- Nije mijenjana business logika parsera, validacije, auto-popune ili decision servisa.
- Nije mijenjan `dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd`.
- Nisu dirani untracked fajlovi: `.worktrees/`, `client.log.lck`, `dist_client/Faktura_20260717_163044.xlsx`, `nul`, `docs/setup/OH_MY_POSH_POWERSHELL7_SETUP.md`, postojeći `project_rooms/*`.

## Verifikacija

- `python -m py_compile` nad 85 izmijenjenih postojećih Python fajlova — OK.
- `python -m pytest mcp_server/tests/test_tools.py tests/unit/test_declaration_validator_tariff_lookup.py tests/unit/test_evidence_adapters_tariff.py tests/test_pdf_plumber_only.py -q`
  - 64 passed
  - 14 skipped
- Provjera starih import putanja — `NO_OLD_IMPORT_REFERENCES`, uz namjerni izuzetak za specijalni `dist_client` `.pyd` most.

## Pronađeni problemi

- Automatska import zamjena je privremeno pogodila `dist_client/services/tariff/tariff_mapping_service.py` i napravila self-import; vraćeno prije commita.
- `tests/test_pdf_plumber_only.py` je lažno padao jer je skenirao `dist/` sa vendorizovanim torch fajlovima i koristio default cp1252 encoding.

## Konflikti / kontradiktorni izvori

Nema aktivnog konflikta. GitNexus `detect_changes` rizik je CRITICAL zbog širine refactora, dok pojedinačni MCP i historical-learning import impact nisu bili HIGH/CRITICAL. Kao važeće je tretirano stvarno testirano ponašanje: importi su migrirani, shims uklonjeni, ciljane provjere prolaze.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `98fc30f` | `feat(mcp): dodaj pretragu bez dijakritickih razlika` |
| `02aa4d5` | `refactor(importi): ukloni stare re-export shimove` |

## Rizici / ograničenja

- Vanjske skripte koje direktno importuju stare top-level shim module više neće raditi; interni projektni pozivaoci su migrirani.
- Regex `~*` može imati drugačiji query plan od `ILIKE`; kod velikog rasta `catalogs.declaration_items` treba ponovo izmjeriti performanse.
- Full `pytest tests/ -q` nije pušten jer postoje poznati širi baseline problemi i ciljano pogođeni testovi su pokrili ovaj scope.

## Potreban follow-up

- Poslije finalnog commita treba pokrenuti `npx gitnexus analyze`.
- Ako postoje eksterne skripte van repozitorija koje koriste stare module, treba ih migrirati na nove putanje.

## Potrebna korisnička potvrda

- Ručno provjeriti MCP pretragu na stvarnoj bazi sa primjerima robe bez kvačica i sa kvačicama.
- Po želji pokrenuti packaged `dist_client` aplikaciju zbog specijalnog `.pyd` mosta i šireg import refactora.
