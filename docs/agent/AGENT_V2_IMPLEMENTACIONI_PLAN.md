# Agent V2 — implementacioni plan inteligentnog agenta i kontrolisane automatizacije

**Datum:** 2026-07-26
**Status:** Spremno za faznu realizaciju
**Namjena:** Kanonski handoff plan za implementaciju unapređenja Carinskog Agenta
**Ciljni ishod:** Pouzdano razumijevanje korisničke namjere i kontrolisana priprema deklaracije do trenutka izvoza ASYCUDA XML-a

---

## 1. Cilj dokumenta

Ovaj dokument je dovoljan da drugi agent preuzme realizaciju bez oslanjanja na
konverzaciju u kojoj je plan nastao. Plan ne predlaže prepisivanje postojećeg
agenta. Cilj je konsolidovati postojeće servise, ukloniti preklapanje namjera,
uvesti strukturisani planer i proširiti sadašnji parcijalni automatski pipeline
do pouzdane provjere spremnosti za XML.

Plan mora biti realizovan fazno. Svaka faza ima:

- precizan scope;
- očekivane fajlove i simbole;
- ulazne i izlazne ugovore;
- testove;
- kriterijume prihvata;
- sigurnosne granice;
- uslove za prelazak na sljedeću fazu.

Nijedna faza ne smije samostalno proširiti dozvole agenta izvan pravila u
`AGENTS.md` i `docs/CONTEXT.md`.

---

## 2. Poslovni problem

Trenutni agent često miješa tri različita korisnička zahtjeva:

1. **prikaz** — korisnik želi vidjeti šta se nalazi u tabu;
2. **provjera** — korisnik želi stručnu validaciju ispravnosti;
3. **akcija** — korisnik želi da agent predloži ili izvrši izmjenu.

Potvrđeni primjeri:

- `Pregledaj naimenovanja` odlazi u generički
  `ApplicationContextService.format_html("naimenovanja")`;
- `Provjeri tabelu u tabu Faktura` može biti presretnuto izrazima
  `tab faktura`, `faktura tab` ili `u fakturi` i završiti kao običan prikaz;
- prikaz Naimenovanja ispisuje samo prvih 20 redova bez stručnog zaključka;
- postojeća provjera naimenovanja dominantno provjerava prazna polja, ne
  semantičku i međutabnu ispravnost;
- `_puna_auto_pipeline()` završava poslije kreiranja naimenovanja i eksplicitno
  ostavlja zaglavlje, završnu provjeru i XML izvoz korisniku.

To nije samo prompt problem. Uzrok je kombinacija:

- širokih lokalnih keyword prečica;
- preklopljenih opisa alata;
- pogrešnog prioriteta routing slojeva;
- tool dispatchera koji uglavnom vidi samo jednu poruku, bez strukturisanog
  stanja deklaracionog procesa;
- validatora različitih formata i neujednačenog obima;
- odsustva planera koji može izvršiti više alata u kontrolisanom redoslijedu.

---

## 3. Važeći izvori i njihov status

| Izvor | Status za ovaj plan | Napomena |
| --- | --- | --- |
| `AGENTS.md` | kanonski | Jezik, arhitektura, GitNexus, testiranje i predaja |
| `docs/CONTEXT.md` | kanonski | Poslovna pravila i poznati bugovi |
| `docs/decisions/001-tool-use-refactoring.md` | aktivan | Tool-first princip |
| `docs/decisions/002-tool-dispatcher-integration.md` | aktivan, nepotpun za Agent V2 | Postojeća dispatcher integracija |
| `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` | djelimično realizovan | Faze A–D uglavnom završene; ovaj plan nastavlja rad |
| `docs/agent/AGENT_INTELLIGENCE_PLAN.md` | aktivan samo za tarifni scoring | Nije opšti plan chat inteligencije |
| `agent_reports/2026-07-19_plan-unapredjenja-agentskog-moda.md` | istorijski handoff | Provjeriti status realizovanih faza kroz kod |
| `agent_reports/2026-07-20_faza-d-standardizovani-rezultati-observability.md` | aktivan | ToolResult, audit i idempotencija su uvedeni |
| aktivni izvorni kod | autoritativan | U slučaju konflikta kod + novija pravila imaju prioritet |

### 3.1 Već implementirani temelji koje ne treba duplirati

- `services/agent/chat/tool_policy.py`
  - `READ_ONLY`, `PROPOSE`, `MUTATE`;
  - fail-closed whitelist poznatih alata.
- `services/agent/chat/tool_result.py`
  - `OK`, `NEEDS_REVIEW`, `UNKNOWN`, `ERROR`;
  - izvor, sljedeća akcija, effect i confirmation metadata.
- `services/agent/chat/audit_log.py`
  - routing, provider, tool i pipeline audit.
- `services/decision/*`
  - jedini dozvoljeni izvor odluka za tarifu, porijeklo i povlasticu.
- `services/agent/validation/declaration_validator_service.py`
  - postojeća završna validacija i spajanje sa `ComplianceCheckService`.
- `services/validation/validation_service.py`
  - postojeći Faktura i Naimenovanje validatori.
- `services/agent/validation/naimenovanja_review_service.py`
  - trenutni pregled i provjera popunjenosti.
- `gui/tabs/agent/workflow_state.py`
  - UI/session state machine; ne predstavlja poslovnu spremnost deklaracije.
- `gui/tabs/agent/services/pipeline_stage_result.py`
  - strukturisan ishod faza automatskog pipeline-a.
- `gui/tabs/agent/services/import_pipeline_service.py::_puna_auto_pipeline`
  - mase, auto-popuna tarifa, validacija, potvrda porijekla/PE i kreiranje
    naimenovanja.
- `gui/tabs/agent/services/xml_workflow_service.py::_izvezi_xml`
  - postojeći XML izvoz; trenutno nije zaštićen punim readiness ugovorom.

---

## 4. Scope lock i sigurnosne granice

### 4.1 Agent smije automatski

- čitati aktivni draft;
- prikazivati stanje;
- pokretati read-only validatore;
- računati mase kroz postojeći servis;
- normalizovati bezbjedne tehničke formate kada poslovna vrijednost ostaje ista;
- primijeniti tačno, ranije potvrđeno mapiranje samo kada postojeća decision
  politika to eksplicitno dozvoli;
- kreirati strukturisan prijedlog;
- nastaviti workflow kada su sve prethodne kapije zadovoljene.

### 4.2 Agent ne smije automatski

- izmišljati tarifni broj, porijeklo, povlasticu ili dokument;
- tumačiti `UNKNOWN`/`NEEDS_REVIEW` kao potvrđen rezultat;
- upisati povlasticu bez eksplicitne potvrde deklaranta;
- zaobići `DeclarationDecisionService`;
- grupisati naimenovanja van `CreateNaimenovanjaService.create_smart_group()`;
- nastaviti poslije blokirajuće validacione greške;
- izvesti XML bez završnog readiness rezultata i korisničke potvrde;
- tretirati warning kao uspjeh bez prikaza korisniku;
- koristiti LLM kao autoritet za poslovnu odluku.

### 4.3 LLM u ciljnoj arhitekturi

LLM je dozvoljen za:

- klasifikaciju složenije korisničke namjere;
- sastavljanje plana iz whitelistanih alata;
- jezičko formatiranje strukturisanih rezultata;
- objašnjavanje potvrđenih nalaza.

LLM nije dozvoljen za:

- generisanje carinskih vrijednosti bez lokalnog dokaza;
- direktnu mutaciju drafta;
- promjenu severity/statusa koji je vratio servis;
- preskakanje workflow kapija.

---

## 5. Ciljna arhitektura

```text
Korisnička poruka
    |
    v
Input Guard
    |
    v
Context Resolver
    |-- konkretan red / prethodni subjekt / pending potvrda
    v
Intent Resolver
    |-- action
    |-- target
    |-- scope
    |-- depth
    |-- effect
    |-- goal
    v
Plan Builder
    |-- jedan alat za prostu namjeru
    |-- više koraka za workflow cilj
    v
Plan Validator
    |-- poznati alati
    |-- argumenti
    |-- ToolPolicy
    |-- preconditions
    |-- confirmation gates
    v
Tool Executor / Workflow Orchestrator
    |
    v
Strukturisani ToolResult / ValidationReport / WorkflowRun
    |
    v
Deterministički renderer
    |
    v
Chat + audit + sljedeća dozvoljena akcija
```

### 5.1 Strogo razdvojene odgovornosti

| Komponenta | Odgovornost | Ne smije |
| --- | --- | --- |
| Context Resolver | Razrješava referencu na red, tab i prethodni subjekt | Birati poslovni zaključak |
| Intent Resolver | Razumije korisničku namjeru | Izvršavati alat |
| Plan Builder | Sastavlja listu koraka | Zaobići whitelist |
| Plan Validator | Provjerava dozvole i preconditions | Mutirati draft |
| Tool Executor | Poziva postojeće servise | Izmišljati rezultat |
| Workflow Orchestrator | Vodi faze i pauze | Nastaviti kroz blokadu |
| Renderer | Prikazuje nalaze | Mijenjati status/severity |
| Audit | Bilježi tok | Rušiti korisničku operaciju |

---

## 6. Novi zajednički ugovori

### 6.1 `AgentIntent`

Preporučena lokacija:

```text
services/agent/chat/intent_model.py
```

Minimalni ugovor:

```python
class IntentAction(str, Enum):
    SHOW = "show"
    VALIDATE = "validate"
    ANALYZE = "analyze"
    PROPOSE = "propose"
    MUTATE = "mutate"
    RUN_WORKFLOW = "run_workflow"
    EXPORT = "export"


class IntentTarget(str, Enum):
    APPLICATION = "application"
    INVOICE = "invoice"
    TARIFFS = "tariffs"
    ORIGIN = "origin"
    ITEMS = "items"
    HEADER = "header"
    DECLARATION = "declaration"
    XML = "xml"


@dataclass(frozen=True)
class AgentIntent:
    action: IntentAction
    target: IntentTarget
    scope: str = "all"
    ordinals: tuple[int, ...] = ()
    depth: str = "summary"
    goal: str = ""
    confidence: float = 1.0
    requires_clarification: bool = False
    clarification_reason: str = ""
```

Pravila:

- `SHOW` nikada ne pokreće validator;
- `VALIDATE` nikada ne vraća samo snapshot;
- `MUTATE` uvijek prolazi `ToolPolicy`;
- `RUN_WORKFLOW` mora proizvesti validiran plan;
- `requires_clarification=True` koristi se samo kada dvije različite akcije
  imaju stvarno različite posljedice i kontekst ne razrješava namjeru.

### 6.2 `ValidationFinding`

Postojeći `ValidationItem` treba ili proširiti kompatibilno ili adaptirati u
jedan zajednički model. Ne praviti paralelne neprevodive modele.

Obavezna polja:

```python
@dataclass(frozen=True)
class ValidationFinding:
    severity: str
    code: str
    target: str
    location: str
    message: str
    evidence: dict
    source: str
    auto_fixable: bool = False
    suggested_action: str = ""
    blocking: bool = False
```

Svaki nalaz mora imati:

- stabilan `code` za testiranje i metrike;
- tačnu lokaciju;
- dokaz bez osjetljivih podataka;
- izvor provjere;
- eksplicitnu blokirajuću prirodu;
- prijedlog sljedeće akcije.

### 6.3 `ValidationSummary`

```python
@dataclass
class ValidationSummary:
    target: str
    checked_count: int
    findings: list[ValidationFinding]
    blocking_count: int
    warning_count: int
    ready: bool
    checks_run: tuple[str, ...]
    checks_skipped: tuple[str, ...] = ()
```

`ready=True` znači samo da su sve obavezne provjere izvršene i da nema blokada.
Nije sinonim za „nema praznih polja“.

### 6.4 `AgentPlan`

Preporučena lokacija:

```text
services/agent/planning/agent_plan.py
```

```python
@dataclass(frozen=True)
class PlanStep:
    id: str
    tool: str
    arguments: dict
    effect: ToolEffect
    preconditions: tuple[str, ...]
    success_condition: str
    failure_policy: str
    requires_confirmation: bool = False


@dataclass
class AgentPlan:
    goal: str
    steps: list[PlanStep]
    current_step: int = 0
    status: str = "pending"
```

Plan mora biti validiran prije prvog izvršenja. LLM rezultat nikada nije direktno
izvršiv dok `PlanValidator` ne potvrdi alat, argumente, effect i preconditions.

### 6.5 Poslovno stanje deklaracije

Ne proširivati postojeći `WorkflowStateManager` tako da miješa UI stanje i
poslovnu spremnost. Uvesti zaseban model, preporučeno:

```text
services/agent/workflow/declaration_workflow_state.py
```

Predložene faze:

```text
EMPTY
FILES_IMPORTED
INVOICE_PARSED
INVOICE_VALIDATED
TARIFFS_RESOLVED
ORIGIN_REVIEW_REQUIRED
ORIGIN_CONFIRMED
MASSES_CALCULATED
ITEMS_CREATED
ITEMS_VALIDATED
HEADER_READY
CROSS_CHECK_PASSED
XML_PREFLIGHT_PASSED
READY_FOR_EXPORT
EXPORTED
BLOCKED
```

Stanje se mora izvesti iz stvarnog drafta i potvrđenih odluka. Ne smije postati
drugi izvor istine koji se može razići sa draftom.

---

## 7. Semantika korisničkih komandi

### 7.1 Kanonska matrica

| Primjer | AgentIntent | Očekivani alat/plan |
| --- | --- | --- |
| `Prikaži Faktura tab` | SHOW / INVOICE | `prikazi_fakturu` |
| `Šta je učitano?` | SHOW / APPLICATION | `pregled_stanja_aplikacije` |
| `Provjeri Faktura tab` | VALIDATE / INVOICE | `provjeri_fakturu` |
| `Pregledaj tabelu Faktura` | VALIDATE / INVOICE / full | `provjeri_fakturu` |
| `Pokaži stavku 17 iz fakture` | SHOW / INVOICE / row | `prikazi_faktura_stavku(17)` |
| `Provjeri tarife` | VALIDATE / TARIFFS | `provjeri_tarife` |
| `Prikaži naimenovanja` | SHOW / ITEMS | `prikazi_naimenovanja` |
| `Pregledaj naimenovanja` | VALIDATE / ITEMS / full | `provjeri_naimenovanja` |
| `Provjeri naimenovanje 5` | VALIDATE / ITEMS / row | `provjeri_naimenovanje(5)` |
| `Provjeri zaglavlje` | VALIDATE / HEADER | `provjeri_zaglavlje` |
| `Provjeri deklaraciju` | VALIDATE / DECLARATION | `validuj_deklaraciju` |
| `Da li je spremno za XML?` | VALIDATE / XML | `provjeri_spremnost_za_xml` |
| `Pripremi deklaraciju` | RUN_WORKFLOW / DECLARATION | višekoračni plan |
| `Nastavi` | RUN_WORKFLOW / current | sljedeći dozvoljeni korak |
| `Izvezi XML` | EXPORT / XML | readiness → potvrda → izvoz |

### 7.2 Jezičko pravilo

- `prikaži`, `pokaži`, `šta ima`, `šta je učitano` → prikaz;
- `provjeri`, `validiraj`, `da li je ispravno`, `šta fali` → validacija;
- `pregledaj` + poslovni objekat → puna validacija, osim kada korisnik eksplicitno
  kaže `samo prikaži`;
- `analiziraj` → dublje poređenje sa istorijom ili pravilima;
- `predloži` → nema automatskog upisa;
- `upiši`, `ispravi`, `primijeni` → mutacija sa ToolPolicy kapijom;
- `pripremi`, `završi`, `nastavi` → workflow namjera.

---

## 8. Faza 0 — baseline, inventar i zaključavanje ponašanja

### Cilj

Prije refaktora napraviti dokaz trenutnog ponašanja i zaštititi postojeće
ispravne tokove.

### Zadaci

1. Pročitati obavezne izvore iz §3.
2. Provjeriti `git status --short`; ne uključivati tuđe izmjene.
3. Provjeriti GitNexus svježinu.
4. Napraviti mapu svih routing ulaza:
   - `_handle_message`;
   - `_resolve_followup`;
   - `_resolve_contextual_request`;
   - `_application_context_scope`;
   - lokalni naimenovanja/faktura regex;
   - `route_local_tool`;
   - LLM Tool Use;
   - regex fallback;
   - plain `ChatWorker`.
5. Evidentirati duplikate i redoslijed prioriteta.
6. Dodati characterization testove za potvrđene pogrešne i ispravne upite.
7. Sačuvati audit izlaz za najmanje 20 reprezentativnih komandi.

### Test fixture

Preporučena lokacija:

```text
tests/fixtures/agent/intent_routing_cases.json
```

Svaki slučaj:

```json
{
  "message": "Provjeri tabelu u tabu Faktura",
  "expected_action": "validate",
  "expected_target": "invoice",
  "expected_tool": "provjeri_fakturu",
  "must_not_call": ["pregled_stanja_aplikacije"],
  "confirmation_required": false
}
```

### Kriterijumi prihvata

- svi postojeći routing slojevi dokumentovani;
- minimalno 50 početnih jezičkih slučajeva;
- poznate greške reproducibilne testom;
- nema izmjene produkcionog ponašanja.

### Procjena

2–3 radna dana.

---

## 9. Faza 1 — jedinstveni Intent Resolver

### Cilj

Ukloniti semantičko preklapanje bez trenutnog razlaganja svih izvršnih servisa.

### Novi/preporučeni moduli

```text
services/agent/chat/intent_model.py
services/agent/chat/intent_resolver.py
services/agent/chat/intent_rules.py
```

### Fajlovi koji će vjerovatno biti izmijenjeni

- `gui/tabs/agent/services/chat_intent_handler.py`
- `services/agent/chat/tool_dispatcher.py`
- `services/agent/chat/tool_definitions.py`
- `services/agent/chat/audit_log.py`
- `tests/unit/test_tool_dispatcher.py`
- `tests/unit/test_application_context_service.py`
- novi `tests/unit/test_agent_intent_resolver.py`

### Implementaciona pravila

1. Jedan resolver određuje action/target/scope prije dispatchera.
2. Lokalna pravila koriste se samo za visoko pouzdane, nedvosmislene obrasce.
3. LLM Tool Use koristi se tek za slučajeve koje pravila ne razriješe.
4. LLM mora vratiti strukturisan intent ili tool call, ne slobodan poslovni
   zaključak.
5. Resolver rezultat se auditira:
   - action;
   - target;
   - confidence;
   - izvor odluke `local|llm|context`;
   - razlog fallbacka.
6. `_application_context_scope()` više ne smije presresti `VALIDATE`.
7. `route_local_tool()` ne smije rutirati svaku poruku koja sadrži
   `tab faktura` u snapshot.
8. Ne uklanjati stare grane dok characterization testovi ne potvrde paritet.
9. Uvesti privremeni compatibility adapter stari intent → novi `AgentIntent`.

### Kriterijumi prihvata

- `Prikaži Faktura tab` daje snapshot;
- `Provjeri/Pregledaj Faktura tab` pokreće validaciju;
- `Prikaži naimenovanja` daje pregled;
- `Provjeri/Pregledaj naimenovanja` pokreće validaciju;
- konkretan red zadržava ispravnu ordinal logiku;
- bez AI providera pouzdani lokalni slučajevi i dalje rade;
- svaki intent fixture daje očekivani rezultat;
- nijedan `MUTATE` intent ne izvršava izmjenu.

### GitNexus prije izmjene

Obavezno provjeriti najmanje:

- `_handle_message`;
- `_application_context_scope`;
- `route_local_tool`;
- `ToolDispatcherWorker`;
- `_resolve_contextual_request`.

HIGH/CRITICAL rezultat zahtijeva project room i handoff upozorenje iz `AGENTS.md`.

### Procjena

3–5 radnih dana.

---

## 10. Faza 2 — jedinstveni validacioni ugovor

### Cilj

Svi validatori vraćaju nalaze koji se mogu agregirati, testirati i prikazati bez
gubitka značenja.

### Pristup

Ne prepisivati postojeće validatore. Uvesti adaptere:

```text
services/agent/validation/finding_model.py
services/agent/validation/invoice_validation_adapter.py
services/agent/validation/items_validation_adapter.py
services/agent/validation/header_validation_adapter.py
services/agent/validation/declaration_validation_adapter.py
```

Adapteri prevode postojeće:

- `ValidationResult`;
- `ValidationItem`;
- `Issue`;
- `NaimenovanjeValidation`;
- decision preflight upozorenja;

u zajednički `ValidationFinding`.

### Obavezni kodovi nalaza

Minimalno:

```text
MISSING_TARIFF
INVALID_TARIFF_FORMAT
TARIFF_NOT_FOUND
UNCONFIRMED_TARIFF
MISSING_ORIGIN
UNCONFIRMED_ORIGIN
UNCONFIRMED_PREFERENCE
PREFERENCE_WITHOUT_EVIDENCE
MISSING_AMOUNT
INVALID_QUANTITY
INVALID_WEIGHT
GROSS_LESS_THAN_NET
INVOICE_TOTAL_MISMATCH
WEIGHT_TOTAL_MISMATCH
DUPLICATE_INVOICE_LINE
MISSING_PACKAGE
INVALID_PROCEDURE
MISSING_STATISTICAL_VALUE
INVALID_RUB31
ITEM_GROUPING_MISMATCH
ASYCUDA_ITEM_LIMIT
HEADER_REQUIRED_FIELD
DOCUMENT_INCONSISTENCY
CROSS_TAB_MISMATCH
XML_PREFLIGHT_BLOCKED
```

### Kriterijumi prihvata

- svaka validacija vraća stabilne kodove i lokacije;
- renderer ne parsira tekst poruke da bi odredio severity;
- nema promjene poslovnih pravila samo zbog adaptacije;
- stari UI može koristiti compatibility renderer;
- testovi pokrivaju konverziju svakog starog tipa rezultata.

### Procjena

3–5 radnih dana.

---

## 11. Faza 3 — stručna provjera Faktura taba

### Cilj

Uvesti `provjeri_fakturu` kao stvarni read-only alat.

### Provjere

1. Popunjenost obaveznih polja.
2. Format tarifnog broja i sufiksa.
3. Postojanje tarife u zvaničnoj tarifi.
4. Status decision evidence za tarifu.
5. Zemlja porijekla i decision status.
6. Povlastica samo uz potvrđen dokaz.
7. Iznos, količina i jedinica mjere.
8. Bruto/neto:
   - nenegativne vrijednosti;
   - bruto nije manje od neto;
   - zbir po fakturi;
   - kontrolna masa.
9. Duplikati i `consumed_paths` posljedice.
10. Faktura/packing-list usklađenost kada oba izvora postoje.
11. Istorijske tarifne razlike samo kroz postojeću decision politiku.
12. Razdvajanje blokada, upozorenja i informacija.

### Tool ugovor

```text
provjeri_fakturu(scope="all" | "selection" | "row", ordinals=[])
```

`ToolEffect.READ_ONLY`.

### Očekivani odgovor

1. zaključak;
2. broj provjerenih stavki;
3. kritične greške;
4. upozorenja;
5. šta nije bilo moguće provjeriti;
6. sljedeća akcija;
7. bez ispisa svih urednih redova.

### Kriterijumi prihvata

- provjerava svih 184 stavki, ne samo prvih N;
- prikazuje samo problematične redove i agregate urednih;
- selection scope poštuje selekciju;
- DB greška nije predstavljena kao „nema problema“;
- rezultat je isti kada se pokrene iz dugmeta i kroz agenta.

### Testovi

- `tests/unit/test_agent_invoice_validation_tool.py`;
- proširiti postojeće Faktura validacione testove;
- realne fakture iz `najavauvoza/`;
- DB nedostupnost;
- 8/10-cifreni tarifni formati;
- bruto/neto edge cases;
- duplikovani kombinovani import.

### Procjena

4–7 radnih dana.

---

## 12. Faza 4 — stručna provjera Naimenovanja taba

### Cilj

Zamijeniti „nema praznih polja“ stvarnom provjerom spremnosti naimenovanja.

### Provjere

1. Sva obavezna polja Rb.31–46.
2. Interni osmocifreni tarifni format i odvojen sufiks.
3. Postojanje tarife.
4. Zemlja i povlastica uz potvrđen evidence.
5. Postupak i prethodni postupak.
6. Pakovanje, broj paketa i oznake.
7. Bruto/neto po naimenovanju.
8. Vrijednost i statistička vrijednost.
9. Dopunska jedinica kada tarifa to zahtijeva.
10. Rub.31:
    - izvor tarifnog opisa;
    - trgovački nazivi;
    - XML limit 280 znakova / 3 linije kroz stvarni builder;
    - overflow marker pravilo.
11. Rub.40 i Rub.44 dokumenti.
12. Grupisanje po:
    - tarifni broj;
    - zemlja porijekla;
    - povlastica;
    - EUR.1 broj.
13. Limit 99 naimenovanja i upozorenje za 98/99 kao operativnu blizinu limita.
14. Zbir masa i vrijednosti prema Faktura tabu.

### Važna granica

Validator ne smije implementirati vlastito grupisanje. Za provjeru koristi isti
`GroupKey`/pravila kao `CreateNaimenovanjaService`.

### Tool ugovor

```text
provjeri_naimenovanja(scope="all" | "row", ordinals=[])
```

Postojeći alat zadržati radi kompatibilnosti, ali promijeniti njegov servisni
rezultat tek nakon characterization testova.

### Kriterijumi prihvata

- svih 98 naimenovanja stvarno je provjereno;
- desetocifreni interni kod se prijavljuje;
- 98/99 daje upozorenje;
- zbir i međutabne razlike su vidljivi;
- uredni redovi se agregiraju;
- detalj jednog reda ostaje dostupan;
- nema lažne poruke „sve uredno“ ako je neka provjera preskočena.

### Testovi

- `tests/unit/test_agent_items_validation_tool.py`;
- Rub.31 real-builder test;
- grupisanje po četiri ključa;
- 98, 99 i 100 naimenovanja;
- zbir mase/vrijednosti;
- nepotvrđena povlastica;
- desetocifreni kod.

### Procjena

4–7 radnih dana.

---

## 13. Faza 5 — provjera Zaglavlja i međutabna usklađenost

### Cilj

Agent mora razlikovati:

- da li je Zaglavlje popunjeno;
- da li je semantički ispravno;
- da li je usklađeno sa Fakturama i Naimenovanjima.

### Provjere Zaglavlja

- tip deklaracije;
- izvoznik, primalac i deklarant;
- valuta, kurs i ukupan iznos;
- uslovi isporuke;
- transport i granična ispostava;
- ukupna bruto/neto masa;
- broj paketa;
- Rb.40;
- priloženi dokumenti;
- Rb.48 se ne prepisuje iz istorijskog XML-a;
- template polja samo kroz `TEMPLATE_FIELDS`.

### Međutabne provjere

- zbir Faktura iznosa = zbir naimenovanja;
- zbir kontrolnih masa = zbir naimenovanja = zaglavlje;
- broj paketa;
- fakture navedene u Rub.31/Rub.44;
- zemlje i povlastice;
- dokumenti header/item;
- aktivni draft je isti u sva tri taba;
- nema miješanja `draft.items` i `draft.invoice_lines`.

### Novi alati

```text
provjeri_zaglavlje
provjeri_usklađenost_tabova
```

Oba `READ_ONLY`.

### Kriterijumi prihvata

- razlikuje missing od mismatch;
- svaki mismatch navodi obje vrijednosti i izvore;
- automatski popunjena polja ne tretira kao korisnički potvrđena ako politika
  zahtijeva potvrdu;
- ne mijenja Zaglavlje tokom provjere.

### Procjena

4–6 radnih dana.

---

## 14. Faza 6 — XML readiness i bezbjedan izvoz

### Cilj

Uvesti jedan autoritativni odgovor na pitanje:

> Da li je deklaracija spremna za ASYCUDA XML izvoz?

### Novi servis

Preporučena lokacija:

```text
services/agent/validation/xml_readiness_service.py
```

Servis orkestrira postojeće validatore i stvarni XML builder preflight. Ne
duplira pravila.

### Obavezne kapije

1. Faktura validacija izvršena.
2. Sve odluke o tarifama u dozvoljenom stanju.
3. Porijeklo potvrđeno gdje je potrebno.
4. Povlastice imaju eksplicitnu potvrdu i dokaz.
5. Mase izračunate i usklađene.
6. Naimenovanja postoje i validna su.
7. Zaglavlje validno.
8. Međutabna provjera prolazi.
9. Limit naimenovanja prolazi.
10. XML builder može izgraditi dokument bez mutiranja produkcionog drafta.
11. Rub.31 finalni format prolazi.
12. Rb.40/Rb.44 dokumenti prolaze.

### Tool ugovor

```text
provjeri_spremnost_za_xml
```

Vraća:

- `READY`;
- `READY_WITH_WARNINGS`;
- `BLOCKED`;
- listu izvršenih provjera;
- listu preskočenih provjera;
- nalaze;
- fingerprint/revision drafta na kojem je provjera rađena.

### Zaštita od stale readiness rezultata

Ako se draft promijeni poslije preflighta, readiness više nije važeći.
Prije izvoza ponovo provjeriti revision/fingerprint.

### XML izvoz

`_izvezi_xml` mora:

1. pozvati readiness;
2. odbiti izvoz na `BLOCKED`;
3. prikazati warninge;
4. tražiti eksplicitnu završnu potvrdu;
5. izvesti XML;
6. auditirati rezultat i putanju bez osjetljivog sadržaja.

### Kriterijumi prihvata

- nije moguće izvesti blokiran draft kroz Agent tok;
- promjena drafta invalidira stari readiness;
- cancel ne kreira fajl;
- greška buildera nije prikazana kao uspjeh;
- izvoz ne mijenja draft;
- rezultat se može testirati bez GUI dijaloga.

### Procjena

5–8 radnih dana.

---

## 15. Faza 7 — Plan Builder i kontrolisani workflow

### Cilj

Podržati ciljeve koji zahtijevaju više uzastopnih alata.

### Novi moduli

```text
services/agent/planning/agent_plan.py
services/agent/planning/plan_builder.py
services/agent/planning/plan_validator.py
services/agent/workflow/declaration_workflow_state.py
services/agent/workflow/declaration_workflow_service.py
```

### Kanonski workflow do XML-a

```text
1. PREPARE_INPUT
2. PARSE_AND_APPLY_IMPORT
3. VALIDATE_INVOICE
4. RESOLVE_TARIFFS
5. REVALIDATE_INVOICE
6. REVIEW_ORIGIN_AND_PREFERENCE
7. WAIT_FOR_DECLARANT_CONFIRMATION
8. CALCULATE_MASSES
9. CREATE_ITEMS
10. VALIDATE_ITEMS
11. PREPARE_HEADER
12. VALIDATE_HEADER
13. CROSS_CHECK
14. XML_PREFLIGHT
15. READY_FOR_EXPORT
16. WAIT_FOR_EXPORT_CONFIRMATION
17. EXPORT
```

### Failure politika

| Rezultat | Ponašanje |
| --- | --- |
| SUCCESS | nastavi |
| WARNING | nastavi samo ako faza dozvoljava; evidentiraj |
| NEEDS_REVIEW | pauziraj i traži ciljanu potvrdu |
| UNKNOWN | pauziraj; ne dozvoli LLM dopunu |
| FAILED | blokiraj |
| CANCELLED | završi bez izmjene |

### Resume

Komanda `Nastavi`:

1. učita trenutno izvedeno poslovno stanje iz drafta;
2. provjeri da li se draft promijenio;
3. ponovi stale faze;
4. nastavi od prve nepotvrđene kapije.

Ne čuvati samo broj indeksa koraka bez provjere stvarnog drafta.

### Integracija sa postojećim pipeline-om

`_puna_auto_pipeline()` prvo obaviti compatibility omotačem, zatim postepeno
pretvoriti faze u pozive `DeclarationWorkflowService`. Ne praviti drugi aktivni
pipeline paralelno.

### Kriterijumi prihvata

- jednostavan upit i dalje koristi jedan alat;
- složen cilj vraća vidljiv plan;
- korisnik vidi trenutnu fazu i razlog pauze;
- workflow se može nastaviti;
- blokada se ne može preskočiti porukom `nastavi`;
- svaki korak vraća strukturisan rezultat;
- pipeline završava na `READY_FOR_EXPORT`, ne na lažnom `COMPLETED`.

### Procjena

7–12 radnih dana.

---

## 16. Faza 8 — nivoi automatizacije i korisničke kapije

### Cilj

Jasno definisati koliko agent smije uraditi bez potvrde.

### Režimi

#### A. Asistirani

- sve analize automatske;
- svaka mutacija traži potvrdu;
- preporučeni početni/default režim.

#### B. Kontrolisana automatizacija

- bezbjedne tehničke operacije automatske;
- decision politika odlučuje šta je dovoljno potvrđeno;
- carinski rizične vrijednosti i dalje traže potvrdu.

#### C. Priprema do XML-a

- workflow vodi cijeli proces;
- obavezne ljudske kapije ostaju;
- XML se ne izvozi bez završne potvrde.

### Obavezne ljudske kapije

- nepouzdana ili konfliktna tarifa;
- porijeklo bez potvrđenog dokaza;
- PE1/PE2/PE3 i EUR.1;
- povlastica;
- ozbiljan mismatch vrijednosti/mase;
- readiness warning koji politika označi za obavezni review;
- finalni XML izvoz.

### Kriterijumi prihvata

- režim ne mijenja poslovnu validaciju;
- viši režim ne smije smanjiti sigurnosne kapije;
- audit bilježi režim;
- promjena režima je eksplicitna i vidljiva;
- testovi dokazuju identičan blokirajući ishod u sva tri režima.

### Procjena

3–5 radnih dana.

---

## 17. Faza 9 — UX, objašnjivost i observability

### Cilj

Agent treba da bude kratak kada je sve uredno i precizan kada postoji problem.

### Standard odgovora validacije

```text
Zaključak
Provjereno
Kritične greške
Upozorenja
Šta nije provjereno
Sljedeći korak
```

### Pravila prikaza

- ne ispisivati svih 184/98 urednih redova;
- prikazati problematične redove;
- grupisati iste nalaze;
- prikazati `... i još N` samo kada postoji način da korisnik otvori ostatak;
- jasno razlikovati:
  - nije pronađeno;
  - nije provjereno;
  - servis nije dostupan;
  - nema problema;
- uz svaki nalaz prikazati izvor;
- dati dugme/akciju za odlazak na konkretan red.

### Observability

Audit događaj treba sadržati:

- session/workflow id;
- intent action/target;
- resolver source;
- selected tool/plan;
- effect;
- provider;
- trajanje;
- rezultat;
- broj nalaza po severity;
- stop reason;
- confirmation outcome;
- draft revision prije/poslije.

Ne logovati JIB, pune partner podatke, sadržaj dokumenata ili tajne.

### Metrike

- intent accuracy;
- tool selection accuracy;
- clarification rate;
- fallback rate;
- unknown-tool rate;
- false-ready rate;
- broj blokiranih opasnih mutacija;
- vrijeme do `READY_FOR_EXPORT`;
- broj ručnih intervencija;
- workflow completion rate;
- broj ponovljenih faza poslije izmjene drafta.

### Procjena

3–5 radnih dana.

---

## 18. Faza 10 — evaluacija, realni dokumenti i release hardening

### 18.1 Intent evaluacija

Minimalno 150 rečenica:

- dijakritika i bez dijakritike;
- tipfeleri;
- kratke komande;
- konkretni redovi;
- follow-up poruke;
- negacije;
- prikaz vs provjera;
- provjera vs mutacija;
- workflow ciljevi.

Metrike:

- action accuracy ≥ 95%;
- target accuracy ≥ 97%;
- opasna mutate klasifikacija: 100%;
- `SHOW`/`VALIDATE` konfuzija < 2%;
- nijedan poznati `VALIDATE` slučaj ne završava snapshotom.

### 18.2 Validaciona evaluacija

Koristiti:

- realne fakture iz `najavauvoza/`;
- poznate bug slučajeve iz `agent_reports/`;
- 8/10-cifrene tarife;
- 98/99/100 naimenovanja;
- više faktura;
- više zemalja;
- PE/EUR.1 slučajeve;
- kombinovane importere;
- nedostupnu bazu;
- konfliktne istorijske podatke.

### 18.3 Workflow E2E

Scenariji:

1. potpuno uredna deklaracija;
2. nedostajuće tarife;
3. konfliktna tarifa;
4. nepotvrđeno porijeklo;
5. povlastica bez dokaza;
6. neuspješno računanje masa;
7. 100 naimenovanja;
8. zaglavlje mismatch;
9. builder greška;
10. korisnik odbija potvrdu;
11. resume poslije ručne ispravke;
12. draft promijenjen poslije preflighta.

### 18.4 Test profili

```text
unit/offline
integration/local SQLite
integration/PostgreSQL
Qt offscreen
real-document regression
Windows build smoke
dist_client parity
```

Mock ne koristiti za SQLite/PostgreSQL poslovne testove gdje projektna pravila
zahtijevaju stvarnu bazu. LLM provider se smije mockovati u routing testovima.

### 18.5 Release kriterijumi

- ciljani testovi zeleni;
- puni test suite bez novih regresija;
- DOC Guard prolazi;
- GitNexus detect_changes pregledan;
- root/dist_client strategija potvrđena;
- PyInstaller/Nuitka build smoke prolazi;
- manual smoke na pravoj deklaraciji;
- XML diff provjeren prema očekivanom izlazu;
- nema automatske povlastice;
- nema izvoza blokiranog drafta.

### Procjena

7–10 radnih dana, zavisno od dostupnosti realnih test scenarija i Windows builda.

---

## 19. Predložena podjela rada na implementacione pakete

Svaki paket treba imati zaseban commit set i agent report.

| Paket | Faze | Može se predati drugom agentu kada |
| --- | --- | --- |
| P0 Baseline | 0 | nema produkcionih izmjena |
| P1 Intent | 1 | characterization fixture zaključan |
| P2 Validation contract | 2 | P1 stabilan |
| P3 Invoice review | 3 | P2 adapteri stabilni |
| P4 Items review | 4 | P2 stabilan |
| P5 Header/cross-check | 5 | P3 i P4 završeni |
| P6 XML readiness | 6 | P5 završen |
| P7 Planner/workflow | 7 | alati i readiness stabilni |
| P8 Automation levels | 8 | P7 stabilan |
| P9 UX/audit | 9 | može djelimično paralelno poslije P2 |
| P10 E2E/release | 10 | sve prethodne faze |

P3 i P4 mogu se realizovati paralelno samo ako oba agenta koriste isti zaključani
`ValidationFinding` ugovor i ne mijenjaju zajedničke router fajlove.

---

## 20. Obavezni testovi po paketu

| Paket | Minimalni test gate |
| --- | --- |
| P0 | postojeći agent routing/tool testovi |
| P1 | intent fixture + dispatcher + context follow-up |
| P2 | adapter unit testovi + stari validator testovi |
| P3 | faktura validation + real invoice regression |
| P4 | naimenovanja + Rub.31 + grouping + 99 limit |
| P5 | zaglavlje + totals/cross-tab |
| P6 | readiness + decision preflight + XML builder |
| P7 | pipeline stage + resume + failure/cancel |
| P8 | mutation gate + confirmation matrix |
| P9 | renderer + audit privacy |
| P10 | puni suite + Windows/dist smoke |

---

## 21. Obavezni GitNexus i git postupak za svakog izvršioca

Prije svake izmjene:

1. pročitati `AGENTS.md` i `docs/CONTEXT.md`;
2. provjeriti `git status --short`;
3. provjeriti indeks;
4. pokrenuti `gitnexus_impact(direction="upstream")` za svaki mijenjani simbol;
5. za HIGH/CRITICAL:
   - napraviti `project_rooms/YYYY-MM-DD_kratak-naziv.md`;
   - prijaviti korisniku rizik prije izmjene;
   - navesti scope lock, tip promjene i test gate;
6. dopuniti GitNexus ručnim `rg` pregledom pozivalaca zbog ranije degradacije
   indeksa;
7. ne dirati nepovezane korisničke izmjene.

Prije commita:

1. ciljani testovi;
2. `py_compile` za izmijenjene Python fajlove;
3. `gitnexus_detect_changes(scope="all")`;
4. pregled očekivanih procesa;
5. DOC Guard;
6. stage samo logičke cjeline;
7. commit bez `--no-verify`;
8. agent report;
9. ažuriranje `docs/CONTEXT.md` samo za ne-očigledne trajne odluke;
10. provjera GitNexus stale statusa i reindex ako je potrebno.

---

## 22. Definition of Done za Agent V2

Agent V2 nije završen samo zato što bolje odgovara na nekoliko chat poruka.
Završen je kada su svi uslovi ispunjeni:

- prikaz, validacija, analiza, prijedlog, mutacija i workflow su jasno razdvojeni;
- potvrđeni routing skup prolazi zadate metrike;
- Faktura, Naimenovanja i Zaglavlje imaju autoritativne read-only provjere;
- postoji međutabna provjera;
- postoji jedan readiness rezultat za XML;
- readiness se invalidira poslije izmjene drafta;
- složen zahtjev proizvodi validiran višekoračni plan;
- workflow se pauzira na `NEEDS_REVIEW`, `UNKNOWN`, `FAILED` i korisničkoj
  potvrdi prema pravilima;
- `Nastavi` ne preskače blokadu;
- agent ne izmišlja carinske vrijednosti;
- mutacije prolaze ToolPolicy i decision service;
- povlastica uvijek ostaje pod eksplicitnom potvrdom;
- XML se ne izvozi bez readiness provjere i završne potvrde;
- audit omogućava rekonstrukciju odluke bez curenja osjetljivih podataka;
- real-document i Windows smoke testovi prolaze;
- nijedan postojeći ispravan ručni workflow nije pokvaren.

---

## 23. Procjena ukupnog obima

| Oblast | Procjena |
| --- | ---: |
| Baseline i intent resolver | 5–8 dana |
| Validacioni ugovor i tri taba | 15–25 dana |
| Međutabna kontrola i XML readiness | 9–14 dana |
| Planer, workflow i režimi automatizacije | 10–17 dana |
| Evaluacija, UX i release hardening | 10–15 dana |
| **Ukupno** | **49–79 radnih dana** |

Procjena uključuje testove, dokumentaciju, realne fakture i release provjere.
Može se smanjiti paralelnim radom na P3/P4/P9, ali centralni router, zajednički
ugovori i workflow orkestrator moraju imati jednog vlasnika po fazi.

---

## 24. Prvi konkretan implementacioni zadatak

Prvi zadatak poslije odobrenja ovog plana treba biti isključivo:

> Implementirati Fazu 0 i Fazu 1: characterization routing dataset, `AgentIntent`
> model i jedinstveni Intent Resolver, tako da se `SHOW` i `VALIDATE` pouzdano
> razlikuju za Faktura i Naimenovanja tab, bez promjene poslovnih validatora.

Scope lock:

- ne proširivati `_puna_auto_pipeline`;
- ne mijenjati carinsku logiku;
- ne mijenjati decision policy;
- ne dodavati automatske mutacije;
- ne refaktorisati cijeli `chat_intent_handler.py`;
- zadržati kompatibilnost postojećih alata.

Obavezni izlaz:

- novi intent ugovor;
- najmanje 50 routing slučajeva;
- testovi za potvrđene pogrešne upite;
- audit izabranog intenta;
- jasna migraciona tačka za Fazu 2.
