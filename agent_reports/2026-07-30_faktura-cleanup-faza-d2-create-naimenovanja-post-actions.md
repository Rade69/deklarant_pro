## Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `services/faktura/models.py`
- `services/faktura/create_naimenovanja_workflow_service.py`
- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/services/faktura/models.py`
- `dist_client/services/faktura/create_naimenovanja_workflow_service.py`
- `tests/unit/test_faktura_create_naimenovanja_workflow_service.py`
- `tests/unit/test_faktura_characterization.py`
- `docs/context/history.md`

## Status izvora

- `AGENTS.md` — aktivan; korisnik je tražio da se pročita prije D2 i pravila su primijenjena.
- `docs/CONTEXT.md` — aktivan; pročitan prije kodiranja.
- `docs/context/history.md` §113 — aktivan za D1 stanje, ali §114 je dodat drugim agentom prije ovog commita.
- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md` — aktivan; D2 je izveden prema manifestu za `Kreiraj Naimenovanja`.

## GitNexus impact

Prije izmjene provjeren je root simbol:

- `Method:gui/tabs/faktura_view.py:FakturaView._on_create_naimenovanja#1`
- rizik: LOW
- impacted count: 4
- direktni calleri: `FakturaView.create_naimenovanja`, `FakturaView._on_export_pdf`, postojeći characterization/unit testovi
- pogođeni procesi: 0

Prije commita pokrenut je `gitnexus_detect_changes(scope="unstaged")`. Rezultat je LOW, ali je obuhvatio i ranije tuđe WIP fajlove u working tree-u (`CLAUDE.md`, dist UI fajlovi, template). Zato je staging ograničen samo na D2 fajlove.

## Reprodukcija prije izmjene

D2 nije bugfix nego refaktor/cleanup. Reprodukcija je bila pregled postojećeg legacy bloka u `_on_create_naimenovanja`: nakon uspješnog kreiranja View je direktno radio dirty/data_changed, PE sync, inspection sync, reload Faktura tabele, reload povezanih tabova, signal i cleanup import memorije.

## Nezavisna provjera

Nije rađena posebna nezavisna checker sesija jer je GitNexus impact LOW i promjena je ograničena na mali adapter bez promjene ponašanja. Umjesto toga dodati su characterization testovi za default plan i redoslijed post-akcija.

## Šta je urađeno

- Dodat `CreateNaimenovanjaPostActionPlan` kao neutralan opis post-akcija nakon uspješnog kreiranja naimenovanja.
- `CreateNaimenovanjaWorkflowService` dobio `build_post_action_plan()`.
- `FakturaView._on_create_naimenovanja` sada poziva `_run_create_naimenovanja_post_actions(...)` umjesto da drži kompletan post-action blok inline.
- Root i `dist_client` kopije su usklađene za izmijenjene fajlove.
- Dodati testovi za default plan i legacy redoslijed izvršavanja.

## Zašto je urađeno

Cleanup Faza D2 smanjuje kompleksnost najosjetljivijeg Faktura workflow-a bez premještanja UI odgovornosti u servis. Service opisuje namjeru, View izvršava UI/logičke akcije koje su vezane za tabove i signale. Time se priprema kasnije precizno brisanje legacy koda, ali se trenutno ponašanje aplikacije čuva.

## Kako je urađeno

U `services/faktura/models.py` uveden je dataclass sa boolean flagovima za svaki legacy post-action korak. `CreateNaimenovanjaWorkflowService.build_post_action_plan()` vraća default plan gdje su svi postojeći koraci uključeni. `FakturaView._run_create_naimenovanja_post_actions()` izvršava plan istim redoslijedom kao raniji inline blok.

## Šta nije dirano

- Nije mijenjan split po zemljama.
- Nije mijenjan preflight dijalog.
- Nije mijenjano core kreiranje kroz `CreateNaimenovanjaService.create_smart_group`.
- Nije mijenjano tarifno učenje kroz `TariffFacade.learn_from_draft`.
- Nije mijenjan javni `_on_create_naimenovanja` / `create_naimenovanja` ugovor.
- Nisu dirani tuđi WIP fajlovi u working tree-u.

## Verifikacija

- `python -m py_compile services/faktura/models.py services/faktura/create_naimenovanja_workflow_service.py gui/tabs/faktura_view.py dist_client/services/faktura/models.py dist_client/services/faktura/create_naimenovanja_workflow_service.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py`
- `python -m pytest tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py tests/unit/asycuda_item_limit_test.py -q` → 73 passed
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_auto_fill_workflow_service.py tests/unit/test_faktura_mass_workflow_service.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_mapping_service.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py tests/unit/asycuda_item_limit_test.py -q -m "not integration"` → 167 passed

## Pronađeni problemi

- Prvi test run je pao jer je `MagicMock` self sakrio novu View metodu, pa se stvarni post-action blok nije izvršio. Test je ispravljen tako da eksplicitno delegira na `FakturaView._run_create_naimenovanja_post_actions`.
- PowerShell sandbox nije mogao pokretati komande zbog `CreateProcessAsUserW 1920`, pa su read-only i test komande pokretane uz odobrenje van sandboxa.
- Working tree je već imao nepovezane izmjene drugih agenata; nisu stageovane.

## Konflikti / kontradiktorni izvori

Nema funkcionalnih kontradikcija. Jedina procesna napomena je da je drugi agent dodao `docs/context/history.md` §114 prije ovog rada, pa je D2 upisan kao §115.

## Commitovi

| Hash | Poruka |
| --- | --- |
| e55caa4 | `refactor(faktura): izdvoji create naimenovanja post akcije` |

## Rizici / ograničenja

Rizik je nizak jer je ponašanje zadržano, ali `Kreiraj Naimenovanja` ostaje poslovno kritičan workflow. Sljedeće faze moraju i dalje imati characterization testove i selektivno staging pravilo zbog paralelnog rada agenata.

## Potreban follow-up

Nastaviti D3 samo ako korisnik potvrdi. Kandidat za D3 je dalje izdvajanje preostalih UI-adapter granica oko preflight/split poruka ili precizno brisanje stvarno mrtvog koda, uz novu impact provjeru.

## Potrebna korisnička potvrda

Korisnik treba ručno, kada bude zgodno, provjeriti jedan live tok: uvoz fakture → `Kreiraj Naimenovanja` → pregled Naimenovanja taba → export XML.
