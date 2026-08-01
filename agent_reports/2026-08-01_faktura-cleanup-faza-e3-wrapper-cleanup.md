## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `dist_client/tests/unit/test_puna_auto_pipeline.py`
- `tests/unit/test_faktura_characterization.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e2-dead-code-audit.md` — aktivan; definiše E3 scope.
- `docs/context/history.md` §121 — aktivan; potvrđuje da su samo dva wrappera E3 kandidati.

## GitNexus impact

`gitnexus-refactoring` skill je korišćen za refactor postupak. U dostupnom tool setu nije bio izložen direktni `impact`, pa je korišćen fallback:

- E2 GitNexus context nalaz za `FakturaView._on_calculate_masses`
- E2 GitNexus context nalaz za `FakturaView._on_auto_fill`
- `rg` inventar pozivalaca prije izmjene
- `gitnexus_detect_changes` prije commita

Rizik je LOW: oba uklonjena simbola su bila trivial wrapperi preko javnih adaptera i nisu imala produkcione pozivaoce.

## Reprodukcija prije izmjene

Ovo nije bugfix nego cleanup poslije E2 audita. Reprodukcija nije primjenjiva; dokaz prije izmjene je E2 audit i `rg` inventar pozivalaca.

## Šta je urađeno

- Uklonjeni `FakturaView._on_calculate_masses` i `FakturaView._on_auto_fill`.
- Ista produkciona izmjena preslikana u `dist_client/gui/tabs/faktura_view.py` zbog root/dist paritet testa.
- Ažurirani komentari u root/dist Agent pipeline servisu da pominju javni `calculate_masses(auto=True)`.
- Root testovi prebačeni sa private-wrapper karakterizacije na javni API i signalni tok.
- `dist_client/tests/unit/test_puna_auto_pipeline.py` poravnat sa root testom jer je još očekivao stari private fallback.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

E2 je pokazao da su ova dva `_on_*` simbola mrtav wrapper sloj koji samo zadržava staru granicu između View-a i Controller-a. Uklanjanje smanjuje lažnu kompleksnost bez promjene ponašanja aplikacije.

## Kako je urađeno

Brisanje je bilo ciljano: uklonjena su samo dva wrappera, dok je implementacija ostala u javnim metodama `calculate_masses()` i `auto_fill()`. Testovi sada provjeravaju da dugmad emituju signale i da uklonjeni private atributi više ne postoje.

## Šta nije dirano

- Nije diran `FakturaView._on_validate_all`.
- Nije diran `FakturaView._on_create_naimenovanja`.
- Nije diran `FakturaView._on_import_finished_legacy`.
- Nije mijenjana poslovna logika masa, auto-popune, validacije ili kreiranja naimenovanja.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...` i ostalim untracked fajlovima.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py gui/tabs/agent/services/import_pipeline_service.py dist_client/gui/tabs/agent/services/import_pipeline_service.py tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_characterization.py`
- `python -m pytest tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_controller.py tests/unit/test_faktura_characterization.py -q` → 64/64 passed
- `python -m pytest dist_client/tests/unit/test_puna_auto_pipeline.py -q` → 17/17 passed
- `rg` potvrda: u root/dist produkcionom `faktura_view.py` više nema `def _on_calculate_masses` ni `def _on_auto_fill`.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je promjena LOW risk i mehanički ograničena. Preporuka: prije sljedeće agresivnije faze uraditi standards/spec review ako se dira validacija ili kreiranje naimenovanja.

## Pronađeni problemi

- Root/dist paritet test je odmah pao nakon root-only brisanja; to je potvrđeno kao ispravan test signal i promjena je preslikana u `dist_client`.
- `dist_client/tests/unit/test_puna_auto_pipeline.py` je bio zastario i očekivao private fallback; poravnat je sa root testom.
- Kombinovani pytest proces koji istovremeno učita root i `dist_client` pipeline testove može kontaminirati import/singleton stanje `TariffFacade`; root set i dist set prolaze odvojeno.

## Odbačene opcije

- Odbačeno: brisati sve `_on_*` metode. Razlog: E2 je pokazao da validacija, kreiranje naimenovanja i legacy import još imaju stvarne pozivaoce.
- Odbačeno: preimenovati `_on_validate_all` u E3. Razlog: prvo treba prebaciti `FakturaTab.validate(auto=True)` na javni adapter i pokriti testovima.

## Konflikti / kontradiktorni izvori

Nema konflikta u produkcionom kodu. Raniji E2 nalaz da se `dist_client` test dug može ostaviti za kasnije promijenjen je nakon što je E3 morao preslikati produkcioni `dist_client` paritet; tada je bilo sigurnije odmah poravnati i odgovarajući dist pipeline test.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 29940e4 | `refactor(faktura): ukloni mrtve view wrappere` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_view.py` i testovi čitani su ciljano oko E3 simbola.

## Rizici / ograničenja

Promjena ne dokazuje ručni GUI E2E tok; oslanja se na postojeće signalne i pipeline testove. Kombinovani root+dist test proces ima import izolacioni problem koji nije riješen u E3 jer nije uzrokovan uklanjanjem wrappera.

## Potreban follow-up

Sljedeći siguran korak je E4: prebaciti `FakturaTab.validate(auto=True)` sa direktnog `_on_validate_all(auto=True)` poziva na javni `view.validate(auto=True)`, uz test koji potvrđuje isti rezultat bez duple validacije.

## Potrebna korisnička potvrda

Za E4 nije potrebna nova poslovna odluka ako scope ostane usko na javni adapter validacije. Za brisanje ili preimenovanje `_on_validate_all` treba posebna potvrda nakon dodatnog audita.
