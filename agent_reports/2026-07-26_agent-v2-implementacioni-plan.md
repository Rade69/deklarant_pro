# Agent V2 — implementacioni plan

## Datum

2026-07-26

## Agent

Codex

## Scope

- `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md`
- analiza postojećeg agent routing-a, tool sloja, validacije, workflow stanja,
  parcijalne automatizacije i XML izvoza
- dokumentacioni zadatak bez izmjene aplikacionog ponašanja

## Status izvora

| Izvor | Status | Upotreba |
| --- | --- | --- |
| `AGENTS.md` | aktivan, kanonski | Projektna pravila i procedura predaje |
| `docs/CONTEXT.md` | aktivan, kanonski | Poslovna pravila i poznati bugovi |
| `docs/decisions/001-tool-use-refactoring.md` | aktivan | Tool-first arhitektura |
| `docs/decisions/002-tool-dispatcher-integration.md` | aktivan, nepotpun za novi cilj | Trenutni dispatcher |
| `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` | djelimično realizovan | Faze A–D i preostali dug |
| `docs/agent/AGENT_INTELLIGENCE_PLAN.md` | aktivan za tarifni scoring | Nije korišten kao opšti chat plan |
| izvještaji od 2026-07-19 i 2026-07-20 | aktivni gdje ih potvrđuje kod | Status ToolPolicy, ToolResult, audit i pipeline rada |
| aktivni kod | autoritativan | Potvrda stvarnog routing-a, validatora i workflow-a |

## GitNexus impact

Nisu mijenjani funkcije, klase ni metode. Prije commita
`gitnexus_detect_changes(scope="all")` vratio je `none`, bez promijenjenih simbola
i pogođenih procesa.

## Šta je urađeno

- napravljen je handoff-ready plan sa 24 sekcije i deset implementacionih faza;
- dokumentovan je potvrđeni uzrok miješanja prikaza i validacije u Faktura i
  Naimenovanja upitima;
- konsolidovani su postojeći temelji umjesto predlaganja paralelnih zamjena:
  `ToolPolicy`, `ToolResult`, audit, decision service, validatori, workflow state,
  pipeline stage result i parcijalni automatski pipeline;
- definisani su ciljni ugovori `AgentIntent`, `ValidationFinding`,
  `ValidationSummary`, `AgentPlan` i poslovno stanje deklaracije;
- razdvojeni su UI/session workflow i poslovna spremnost deklaracije;
- definisana je semantika komandi za prikaz, validaciju, analizu, prijedlog,
  mutaciju, workflow i XML izvoz;
- definisane su stručne provjere Faktura, Naimenovanja i Zaglavlje taba,
  međutabna usklađenost i XML readiness;
- dodani su stale-readiness zaštita, kontrolisani resume, nivoi automatizacije,
  obavezne ljudske kapije, audit metrike i release kriterijumi;
- plan je podijeljen u implementacione pakete sa zavisnostima i test gate-ovima;
- preciziran je prvi implementacioni zadatak: Faza 0 + Faza 1, bez širenja
  poslovne automatizacije.

## Zašto je urađeno

Korisnik želi unaprijediti agenta do kontrolisane pune pripreme deklaracije prije
XML izvoza i tražio je plan koji može predati drugom agentu. Postojeće ponašanje
pokazuje da keyword routing može pretvoriti zahtjev za validaciju u običan prikaz
stanja. Raniji planovi pokrivaju tarifni scoring i sigurnosne faze A–D, ali ne
daju jedinstven, aktuelan plan za intent model, validatore sva tri taba, planer,
poslovni workflow, XML readiness i release evaluaciju.

## Kako je urađeno

- pregledani su postojeći planovi, decision dokumenti i noviji agent reporti;
- pregledani su aktivni routing redoslijed, tool definicije, lokalni dispatcher,
  ToolPolicy, ToolResult, UI workflow state i pipeline result;
- pregledani su Faktura, Naimenovanja, kompletna deklaraciona validacija,
  decision preflight i XML export tačke;
- potvrđeno je da `_puna_auto_pipeline()` trenutno završava poslije kreiranja
  naimenovanja i ne priprema zaglavlje niti readiness;
- plan je napisan tako da svaka faza ima scope, fajlove, ugovore, testove,
  kriterijume prihvata, procjenu i GitNexus obaveze.

## Šta nije dirano

- nije mijenjan aplikacioni kod;
- nisu mijenjani router, tool definicije, validatori, pipeline ili XML builder;
- nije mijenjan `docs/CONTEXT.md`, jer je već imao zatečene korisničke izmjene;
- nisu dirani `AGENTS.md`, `CLAUDE.md`, admin panel, postojeći test i ostali
  zatečeni/nepraćeni fajlovi;
- nije sinhronizovan `dist_client`;
- nije pokrenuta implementacija Faze 0 ili Faze 1.

## Verifikacija

- `git diff --check` je nakon uklanjanja četiri trailing-whitespace znaka čist;
- skeniranje plana nije pronašlo ćirilične znakove;
- GitNexus detect changes: `none`, 0 simbola, 0 procesa;
- pre-commit hook je prošao;
- commit je sadržao samo novi plan;
- ručni `bash scripts/doc_link_checker.sh .` nije mogao biti pokrenut jer `bash`
  nije dostupan u ovom Windows PowerShell okruženju;
- aplikacioni testovi nisu pokretani jer nije mijenjan kod.

## Pronađeni problemi

- postojeći planovi imaju preklapajući scope i različite stepene realizacije;
- `ApplicationContextService` i lokalni keyword routing presreću dio zahtjeva za
  validaciju;
- postojeći UI `WorkflowStateManager` nije model poslovne spremnosti deklaracije;
- validacioni servisi vraćaju više neujednačenih modela rezultata;
- trenutna puna automatizacija nije puna do XML-a;
- radno stablo je već bilo prljavo prije zadatka.

## Konflikti / kontradiktorni izvori

Stari dokumenti na pojedinim mjestima opisuju faze kao planirane, iako su
`ToolPolicy`, mutation gate, provider unifikacija, strukturisani rezultati i audit
kasnije implementirani. Aktivni kod i noviji izvještaji tretirani su kao važeći.
Novi plan eksplicitno označava starije dokumente kao djelimično realizovane i ne
ponavlja završene faze kao novi posao.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `5557949` | `docs(agent): dodaj plan realizacije Agent V2` |

## Rizici / ograničenja

- procjene trajanja zavise od kvaliteta realnih test slučajeva i Windows build
  verifikacije;
- GitNexus konceptualna pretraga je degradirana bez FTS indeksa, pa su nalazi
  potvrđivani direktnim kodom;
- plan je širok i mora se realizovati fazno; paralelna izmjena centralnog routera
  od više agenata nije bezbjedna;
- DOC Guard treba ponoviti u okruženju koje ima `bash`.

## Potreban follow-up

1. Korisnik potvrđuje početak Faze 0 + Faze 1.
2. Izvršilac pravi project room ako impact centralnih routing simbola bude HIGH
   ili CRITICAL.
3. Prvo se zaključava routing dataset, zatim uvodi `AgentIntent`.
4. Poslovni validatori i puna automatizacija ostaju netaknuti do narednih faza.

## Potrebna korisnička potvrda

- potvrditi da se implementacija pokrene od Faze 0 + Faze 1;
- potvrditi da `pregledaj` nad poslovnim tabom podrazumijeva stručnu validaciju,
  dok `prikaži/pokaži` znači samo prikaz sadržaja.
