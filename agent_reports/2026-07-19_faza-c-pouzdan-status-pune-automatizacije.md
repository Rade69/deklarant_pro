# Agent Report — 2026-07-19: Faza C — pouzdan status pune automatizacije

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + dist_client mirror
- `gui/tabs/agent/services/import_pipeline_service.py` + dist_client mirror
- `gui/tabs/agent/services/pipeline_stage_result.py` (novo) + dist_client mirror
- `tests/unit/test_pipeline_stage_result.py` (novo)
- `tests/unit/test_puna_auto_pipeline.py` (novo)

Realizovana **Faza C** iz `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` §7.
Faze D–F nisu rađene.

---

## Status izvora

- Plan (dograđen §5.6/§6.6/§7.7/§10.4 istom sesijom ranije) — aktivan, jedini izvor.
- `agent_reports/2026-07-19_faza-a-...md`, `agent_reports/2026-07-19_faza-b-...md` — aktivni,
  bez preklapanja sa scope-om ove faze.

---

## GitNexus impact

Prije izmjene provjerene 4 View metode (`_on_calculate_masses`, `_on_auto_fill`,
`_on_validate_all`, `_on_create_naimenovanja`) i `_puna_auto_pipeline` —
sve **LOW/MEDIUM** rizik (pozivane iz UI dugmadi + jednog internog pipeline
poziva, bez šireg call-graph-a). `project_rooms/*.md` fajl nije bio obavezan.

Nakon commitova, `gitnexus_detect_changes(scope="all")`: **risk_level: low**,
121 promijenjenih simbola (root + dist_client parovi, uglavnom lokalne
varijable unutar prepisane `_puna_auto_pipeline`), **0 affected_processes**.

---

## Šta je urađeno

### 1. `pipeline_stage_result.py` (novo)

`PipelineStageStatus` enum (SUCCESS/WARNING/FAILED/WAITING_CONFIRMATION/
CANCELLED), `PipelineStageResult` dataclass (`stage`, `status`, `message`,
`reason`, `can_continue`, `stats`), `overall_outcome()` — agregira listu
rezultata faza u `COMPLETED/PARTIAL/FAILED/CANCELLED`. Namjerno odvojen
model od `WorkflowState` (vidi "Šta nije dirano").

### 2. `faktura_view.py` — 4 View metode dobile strukturisan povratni ishod

- `_on_calculate_masses(auto=False) -> bool`: svi bare `return` na bailout
  putanjama promijenjeni u `return False`, uspješan put dobija `return True`.
- `_on_auto_fill(auto=False)`: bez promjene ugovora povratne vrijednosti
  (već je vraćao `MappingResult`/`None`), ali exception handler sad guarda
  `error_handler.handle_auto_fill_error()` sa `if not auto`.
- `_on_validate_all(auto=False) -> tuple[bool, int, int]`: vraća
  `(ok, error_count, warning_count)`; bailout `(False, 0, 0)`; exception
  `(False, -1, -1)` uz guardovan dijalog. Poziv
  `_run_historical_tariff_validation` promijenjen sa `modal=auto` na
  `auto=auto` (vidi tačku 3).
- `_on_create_naimenovanja(auto=False) -> bool`: bailout tačke (nema
  stavki, korisnik otkazuje pre-flight dijalog) vraćaju `False`, uspjeh
  `True` prije `except`, exception handler guardovan sa `if not auto`.

### 3. Otkriven i popravljen skriven bug: blokirajući modal u auto modu

`_run_historical_tariff_validation(self, modal=False, auto=False)` — ranije
je pozivana sa `modal=auto`, što znači: kad je pipeline u punoj automatizaciji
i postoje istorijski prijedlozi tarifa, funkcija bi otvorila **blokirajući
Qt modalni dijalog** (`TariffValidationDialog`) i čekala korisnika — potpuno
suprotno namjeri "auto mod = bez dijaloga", i praktično bi zamrznulo pipeline
bez ijedne poruke u chatu zašto ništa dalje ne radi. Dodat zaseban `auto`
parametar: kad je `True` i postoje prijedlozi, funkcija samo loguje broj
prijedloga i vraća se (dijalog se uopšte ne otvara), umjesto da bude modalna.

### 4. `import_pipeline_service.py` — `_puna_auto_pipeline` prepisan

Svaka od 5 faza (mase / auto-popuna / validacija / potvrda deklaranta /
naimenovanja) sad gradi `PipelineStageResult` i dodaje ga u `results` listu.
Kritične faze (pad mase, validacija sa kritičnim greškama, pad naimenovanja)
odmah pozivaju novi `_finish_puna_auto_pipeline(ctrl, chat, results)` helper
i **prekidaju** — više se ne nastavlja na sljedeću fazu nakon kritičnog pada.
Stara funkcija je bila monolitna: nakon `except` bloka na pojedinoj fazi
tok bi nastavio dalje kroz preostale pozive kao da se ništa nije desilo,
a krajnja poruka je uvijek tvrdila uspjeh/djelimičan uspjeh bez stvarne
provjere šta se prije toga pokvarilo.

---

## Zašto je urađeno

Plan §7 traži "pouzdan status pune automatizacije" — korisnik u chatu mora
dobiti tačnu informaciju da li je pipeline stvarno završen, djelimično
završen (upozorenja, ali nastavljeno), ili zaustavljen zbog kritične greške.
Prije ove izmjene, View metode nisu imale konzistentan povratni ugovor
(neke `None`, neke bez `return` vrijednosti), pa je `_puna_auto_pipeline`
morao nagađati ishod iz side-efekata — što je i dovelo do gore opisanog
"tihog nastavka nakon pada".

---

## Kako je urađeno

Minimalno-rizičan pristup: pročitane su SVE `return`/`except` tačke u sve
4 View metode prije bilo kakve izmjene (ne parcijalno), da se osigura da
nijedna postojeća putanja ostane bez eksplicitne povratne vrijednosti.
Interna poslovna logika metoda nije mijenjana — samo signature (`auto=`
parametar gdje ga nije bilo) i povratne vrijednosti/guard na dijalozima.
Ovo je namjerno manje ambiciozno od plan-ove sugestije da se logika izloži
kroz servisni sloj — plan-ovi vlastiti acceptance kriterijumi (§7) su
ponašanje-fokusirani, ne strukturni, pa je rizik/napor prevagnuo protiv
šireg refaktora u ovom prolazu.

---

## Šta nije dirano

- `WorkflowState` (`gui/tabs/agent/workflow_state.py`) — namjerno NIJE
  povezan sa `PipelineStageResult`. Otkriveno da `WorkflowState.APPLYING`
  nije dostižan iz `WorkflowState.COMPLETED`, stanja koje `agent_controller.py`
  postavlja neposredno prije poziva `_puna_auto_pipeline` — dodavanje
  tranzicija bi zahtijevalo restrukturiranje state machine-a, van scope-a
  ove faze. `PipelineStageResult` ostaje uži, zaseban koncept (plan sam
  upozorava da se ne smiju duplirati dva nezavisna izvora workflow stanja).
- `ErrorHandler` klasa sama (dijeljena, koristi se šire u aplikaciji) —
  guard je dodat na mjestu poziva unutar 3 pogođene View metode, ne unutar
  same klase (viši rizik da bi izmjena dijeljene klase pogodila druge
  pozivaoce van scope-a).
- Interna poslovna logika sve 4 View metode (kalkulacija masa, auto-popuna
  matching, validacione provjere, kreiranje naimenovanja) — netaknuta.
- Faze D–F plana.

---

## Verifikacija

```
python -m pytest tests/unit/test_pipeline_stage_result.py tests/unit/test_puna_auto_pipeline.py -q
→ 17 passed

python -m pytest tests/unit tests/integration -q  (puni run, ranije u sesiji)
→ 715 passed, 44 skipped, 6 xfailed, 12 failed
  (svih 12 pada pretpostojeće/okolinsko: 10x PostgreSQL server privremeno
  nedostupan (192.168.0.25), 2x poznata Pi/Codex regresija u
  test_tariff_validation_dialog.py, nepovezano sa ovom sesijom)

python -m py_compile <8 fajlova: root+dist_client parovi svih izmijenjenih/
novih fajlova + 2 nova test fajla> → OK, 0 grešaka

diff (bez BOM) <root> <dist_client> za sva 3 izmijenjena/nova fajla → IDENTIČNI

mcp__gitnexus__detect_changes(scope="all") nakon commitova
→ risk_level: low, affected_processes: []
```

---

## Pronađeni problemi

- Blokirajući modalni dijalog u `_run_historical_tariff_validation` pri
  `auto=True` (vidi "Šta je urađeno" tačka 3) — ozbiljan bug koji plan
  nije eksplicitno predvidio, otkriven tek čitanjem svih poziva unutar
  `_on_validate_all` prije izmjene.
- `ErrorHandler` pozivi u 3 View metode bez `auto`-guard-a — istog uzroka
  (dijalog usred bezglave automatizacije), popravljeno na mjestu poziva.

---

## Konflikti / kontradiktorni izvori

Nema. Plan §7 je bio dovoljno jasan da se implementira bez dodatnih
korisničkih odluka usred rada.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `0442396` | feat(agent): uvedi PipelineStageResult model za faze pune automatizacije |
| `994785e` | fix(agent): zaustavi punu automatizaciju odmah nakon kriticne greske faze |
| `1e3fcfc` | test(agent): pokrij PipelineStageResult i _puna_auto_pipeline (Faza C) |

---

## Rizici / ograničenja

- Testovi za `_puna_auto_pipeline` koriste `MagicMock` za `ctrl`/`fw`/`chat`
  (plan-om dozvoljeno za ovaj sloj), ne pravu Qt/DB integraciju — ne
  pokrivaju stvarno ponašanje `TariffValidationDialog`-a ili prave baze.
- `_on_auto_fill` povratni ugovor NIJE mijenjan (već je vraćao smislenu
  vrijednost) — ako se ikad promijeni ugovor te metode, `_puna_auto_pipeline`
  treba ponovo provjeriti (koristi `matched_items` atribut rezultata).
- `WorkflowState` i dalje ne prati faze pipeline-a — ako neki drugi dio UI-a
  (npr. status traka) očekuje da vidi `APPLYING` tokom pune automatizacije,
  to i dalje neće raditi bez zasebnog zadatka.

---

## Potreban follow-up

- Faze D (standardizovani rezultati/observability), E (integracioni testovi
  prije refaktora), F (razlaganje `ChatIntentHandler`) čekaju odluku
  korisnika o nastavku.
- Ručna provjera u pravoj aplikaciji: pokrenuti punu automatizaciju na
  fakturi koja ima istorijske tarifne prijedloge i potvrditi da se dijalog
  VIŠE ne pojavljuje (ranije bi se zamrznuo pipeline).

---

## Potrebna korisnička potvrda

- Ručno testirati punu automatizaciju (dugme u agent tabu) na realnoj
  fakturi sa i bez kritičnih validacionih grešaka, potvrditi da se poruke
  u chatu ("završena!" / "zaustavljena" / "djelimično") poklapaju sa
  stvarnim ishodom.
