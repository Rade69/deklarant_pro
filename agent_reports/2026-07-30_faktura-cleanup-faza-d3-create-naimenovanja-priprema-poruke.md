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
- `docs/context/history.md`

## Status izvora

- `AGENTS.md` — aktivan; primijenjena pravila za refaktor, selektivni staging i agent report.
- `docs/CONTEXT.md` — aktivan; pročitan prije kodiranja.
- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md` — aktivan; D3 je nastavak D1/D2 podfaza za `Kreiraj Naimenovanja`.
- `agent_reports/2026-07-30_faktura-cleanup-faza-d2-create-naimenovanja-post-actions.md` — aktivan; D3 se nadovezuje na post-action plan.

## GitNexus impact

GitNexus `context` za `Method:gui/tabs/faktura_view.py:FakturaView._on_create_naimenovanja#1` pokazao je mali broj direktnih pozivalaca:

- `FakturaView.create_naimenovanja`
- `FakturaView._on_export_pdf`
- characterization test za `draft_uid` učenje

Outgoing reference uključuju `_offer_split_by_country`, `_run_create_naimenovanja_post_actions`, `analyse_preflight`, `SafeMessageBox`/`QMessageBox` prikaze i `CreateNaimenovanjaWorkflowService`. `impact` alat nije bio izložen u trenutnom tool setu, pa je `context` korišćen kao fallback prije izmjene, a `detect_changes` ostaje obavezna provjera prije commita.

## Reprodukcija prije izmjene

D3 nije bugfix nego refaktor/cleanup. Prije izmjene `_on_create_naimenovanja` je i dalje inline radio tri različite odgovornosti: pripremu draftova/linija, odluku da li ponuditi split, i sklapanje korisničkih success/warning poruka. Core kreiranje je već bilo u servisu iz D1, a post-akcije u planu iz D2.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je promjena ograničena i testabilna. Dodati su servisni testovi za split odluku, auto tok, multi-draft obradu, single success poruku i ASYCUDA overflow warning poruku.

## Šta je urađeno

- Dodati neutralni modeli `CreateNaimenovanjaPreparationResult` i `CreateNaimenovanjaUserMessage`.
- `CreateNaimenovanjaWorkflowService.prepare(...)` sada centralizuje izbor draftova, skupljanje linija i odluku da li interaktivni tok treba ponuditi split po zemljama.
- `CreateNaimenovanjaWorkflowService.build_success_message(...)` generiše neutralnu poruku za single, multi-draft i ASYCUDA 99 overflow rezultat.
- `FakturaView._on_create_naimenovanja` je skraćen: View i dalje prikazuje split/preflight i QMessageBox, ali tekst/odluka dolaze iz servisa.
- Root i `dist_client` kopije su usklađene.

## Zašto je urađeno

`Kreiraj Naimenovanja` ostaje najrizičniji workflow u Faktura cleanup-u. D3 smanjuje kompleksnost bez aktiviranja novog Controller create puta i bez brisanja legacy handlera. Time se dobija bolja testabilnost preflight/split/result granice, uz očuvanje istog runtime ponašanja.

## Kako je urađeno

Servis vraća neutralne dataclass rezultate bez Qt zavisnosti. View ih koristi kao instrukcije: ako `should_offer_split=True`, poziva postojeći `_offer_split_by_country`, zatim ponovo priprema draftove jer split mijenja `self._multi_drafts`. Poruke se prikazuju kroz mali View adapter `_show_create_naimenovanja_message`.

## Šta nije dirano

- Nije mijenjan `CreateNaimenovanjaService.create_smart_group`.
- Nije mijenjano tarifno učenje ni ledger `draft_uid`.
- Nije mijenjan preflight dijalog.
- Nije mijenjan split servis ni sama split logika.
- Nije brisan legacy `_on_create_naimenovanja`.
- Nije aktiviran Controller create kao produkciona zamjena.
- Nisu dirane tuđe WIP izmjene u working tree-u.

## Verifikacija

- `python -m py_compile services/faktura/models.py services/faktura/create_naimenovanja_workflow_service.py gui/tabs/faktura_view.py dist_client/services/faktura/models.py dist_client/services/faktura/create_naimenovanja_workflow_service.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py`
- `python -m pytest tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py tests/unit/asycuda_item_limit_test.py -q` → 78 passed
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_auto_fill_workflow_service.py tests/unit/test_faktura_mass_workflow_service.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_mapping_service.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py tests/unit/asycuda_item_limit_test.py -q -m "not integration"` → 172 passed

## Pronađeni problemi

- GitNexus `impact` alat nije bio izložen nakon tool discovery-ja; korišćen je `context` kao pre-change fallback.
- Working tree i dalje sadrži nepovezane izmjene drugih agenata (`CLAUDE.md`, dist UI fajlovi, untracked fajlovi). Nisu stageovane.

## Konflikti / kontradiktorni izvori

Nema funkcionalnih kontradikcija. D3 je nastavak D1/D2 i zadržava zabranu iz manifesta: ne brisati `_on_create_naimenovanja` prije punog pariteta i korisničkog E2E.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): izdvoji create naimenovanja pripremu` |

## Rizici / ograničenja

Rizik je nizak do srednji po poslovnoj važnosti: promjena ne mijenja core kreiranje, ali se nalazi u kritičnom workflow-u. Ručni E2E na realnoj fakturi ostaje obavezan prije Faze E i bilo kakvog brisanja fallback-a.

## Potreban follow-up

Sljedeće je stabilizacioni pregled D1-D3 cjeline ili Faza E tek nakon korisničkog E2E. Prije brisanja treba potvrditi da nema preostalih privatnih pozivalaca koji zavise od legacy ponašanja.

## Potrebna korisnička potvrda

Korisnik treba ručno provjeriti: uvoz realne fakture → `Kreiraj Naimenovanja` u ručnom toku → pregled Naimenovanja/Zaglavlje → XML export smoke test.
