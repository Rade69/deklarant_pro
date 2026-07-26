# Agent V2 — implementacioni plan inteligentnog agenta i kontrolisane automatizacije

**Datum:** 2026-07-26
**Verzija:** 2.1 (v2.0 je commit `e62eae8`; v1.0 je commit `5557949` — oba dostupna kroz `git show <hash>:docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md`)
**Status:** Spremno za faznu realizaciju
**Namjena:** Kanonski handoff plan za implementaciju unapređenja Carinskog Agenta
**Ciljni ishod:** Pouzdano razumijevanje korisničke namjere i kontrolisana priprema deklaracije do trenutka izvoza ASYCUDA XML-a

---

## 1. Cilj dokumenta

Ovaj dokument je dovoljan da drugi agent preuzme realizaciju bez oslanjanja na
konverzaciju u kojoj je plan nastao. Plan ne predlaže prepisivanje postojećeg
agenta.

Svaka tvrdnja o postojećem ponašanju u §3 je **provjerena u kodu i navedena sa
`fajl:linija`**. Izvršilac ne treba ponovo dokazivati dijagnozu — treba je
iskoristiti.

Plan mora biti realizovan fazno. Svaka faza ima precizan scope, očekivane
fajlove i simbole, ulazne i izlazne ugovore, testove, kriterijume prihvata,
sigurnosne granice i uslove za prelazak na sljedeću fazu.

Nijedna faza ne smije samostalno proširiti dozvole agenta izvan pravila u
`AGENTS.md` i `docs/CONTEXT.md`.

---

## 2. Šta je promijenjeno u odnosu na v1.0

Ovaj odjeljak postoji zato da izvršilac koji je čitao v1.0 ne radi po zastarjelim
pretpostavkama. Četrnaest suštinskih izmjena (stavke 12 i 14 su dodane u v2.1,
poslije eksplicitne korisničke odluke od 2026-07-26 — vidi §18/§19/§25):

| # | Izmjena | Razlog |
| --- | --- | --- |
| 1 | Uvedena **Faza −1 (blokirajući preduslovi)** prije Faze 0 | Četiri preduslova su bila skrivena unutar kasnijih faza i tiho bi im udvostručila obim |
| 2 | `tool_definitions.py` prebačen iz „vjerovatno izmijenjen“ u **primarni obavezni scope Faze 1** | SYSTEM_PROMPT i opisi alata *sami uče LLM pogrešno mapiranje* (§3.2) — resolver bez toga popravlja samo lokalnu granu |
| 3 | Broj alata se **smanjuje sa 12 na 8** (parametrizovani `prikazi`/`provjeri`) umjesto rasta na 19 | v1.0 je implicitno tražila 7 novih alata; veći skup alata obara tačnost LLM izbora, a v1.0 istovremeno traži ≥95% |
| 4 | Imena alata **ograničena na ASCII** | v1.0 je predlagala `provjeri_usklađenost_tabova` — Groq/OpenAI odbijaju ime van `^[a-zA-Z0-9_-]{1,64}$` |
| 5 | Poslovno stanje modelovano kao **kapije (gates)**, ne kao enum od 16 stanja | Linearni enum poziva na upis polja u draft i drugi izvor istine |
| 6 | Dodata obaveza **`revision`/`fingerprint` na draftu** kao zaseban rani zadatak | `core/draft/` ga nema; readiness iz Faze 6 bez njega ne može postojati |
| 7 | Dodat zahtjev **izvršavanja validacije van UI threada** + progress | Faza 3 nad stotinama stavki radi PG lookup; danas se sličan kod izvršava na UI threadu (§3.5) |
| 8 | Dodat zahtjev **single-flight brave i injektabilne potvrde** | `_puna_auto_pipeline` je re-entrantan i vezan za `QMessageBox` (§3.4) |
| 9 | Dodata **dist_client strategija kao odluka Faze −1**, ne kao release provjera | Svaki router fajl postoji dvaput; drift je ranije proizveo crash bug |
| 10 | Dodat **kill-switch** za cijeli V2 routing | Windows klijent (.55) je radna mašina; regresija mora biti opoziva bez builda |
| 11 | Inventar konkurentnih validacionih tipova proširen sa 4 na **8 + 5 kolizija imena** | v1.0 je nabrajala samo dio; adapteri bi importovali pogrešnu klasu |
| 12 | Faze 7 i 8 (planer, režimi automatizacije) su **obavezan scope**, ne uslovan | Eksplicitna korisnička odluka (2026-07-26): jedna komanda pokreće cijeli proces do XML-a, agent vodi tok uz pauze na kapijama |
| 13 | Kriterijumi prihvata **oslobođeni hardkodovanih brojeva** (184/98) | To su brojevi jedne konkretne deklaracije, ne ugovor |
| 14 | Procjene po fazi preformulisane kao **relativna složenost za paralelan agent-rad**, ne serijski ljudski radni dani | Realizacija ide kroz više paralelnih AI agenata; stvarno ograničenje je redoslijed kapija i token/poruka budžet, ne brzina pisanja koda (§25) |

---

## 3. Verifikovana dijagnoza

Trenutni agent miješa tri različita korisnička zahtjeva: **prikaz**, **provjera**,
**akcija**. Uzrok nije prompt, nego pet konkretnih mjesta u kodu.

### 3.1 Dvostruka keyword tabela na dva nivoa

Ista odluka „koja poruka je snapshot“ postoji na **dva nezavisna mjesta**:

- `gui/tabs/agent/services/chat_intent_handler.py:760` — `_application_context_scope()`
- `services/agent/chat/tool_dispatcher.py:63` — `route_local_tool()`

Popravka jednog ne popravlja drugi. Konkretno:

```python
# chat_intent_handler.py:765-771 — "pregledaj" je tretiran kao ZELJA ZA PRIKAZOM
wants_view = any(kw in msg for kw in ("pogledaj", "pregledaj", "pokaži", ...))
```

```python
# tool_dispatcher.py:71-72 — bezuslovno, bez ijedne provjere glagola
if any(k in msg for k in ("tab faktura", "faktura tab", "u fakturi")):
    return ToolCall("pregled_stanja_aplikacije", {"scope": "faktura"})
```

### 3.2 Definicije alata same uče LLM pogrešno mapiranje

Ovo je nalaz koji v1.0 nije imala i koji mijenja prioritet Faze 1.

- `services/agent/chat/tool_definitions.py:172-175` — opis alata
  `prikazi_naimenovanja` doslovno kaže: *„Koristi za 'pregledaj naimenovanja'“*.
- `services/agent/chat/tool_definitions.py:38` — SYSTEM_PROMPT pravilo 17:
  *„Za 'pogledaj tab faktura' … → pregled_stanja_aplikacije“*.

Posljedica: čak i savršen lokalni Intent Resolver ne popravlja LLM granu.
**`tool_definitions.py` mora biti izmijenjen u istom paketu kao resolver, ne kasnije.**

### 3.3 Mrtva grana — kod koji rješava problem se ne izvršava

U `_handle_message`:

- linija 1024 — `_application_context_scope()` presreće i vraća `return`;
- linija 1030 — `_is_naimenovanja_review_request()` / `_is_naimenovanja_validation_request()`.

Za poruku `Pregledaj naimenovanja` prva grana uvijek pobjeđuje. Funkcija
`_is_naimenovanja_validation_request` — napisana upravo da razlikuje prikaz od
provjere — **nedostižna je za taj izraz**.

Dodatno, u `_application_context_scope:781-786` provjera `faktura` ide **prije**
`naimenov`, pa `pregledaj naimenovanja iz fakture` vraća `faktura`.

> **Obaveza za Fazu 0:** mapa routinga mora mjeriti *dostižnost* svake grane, ne
> samo je nabrojati. Grana koja se ne izvršava se ne popravlja — briše se ili joj
> se mijenja redoslijed.

### 3.4 Automatski pipeline je vezan za UI thread i re-entrantan

`gui/tabs/agent/services/import_pipeline_service.py:203` `_puna_auto_pipeline`:

- poziva `QApplication.processEvents()` između faza (linije 216, 236, 267, 310…);
- poziva `QMessageBox.question(...)` inline (linija 314);
- poziva GUI metode widgeta: `fw._on_calculate_masses()`, `fw._on_auto_fill()`,
  `fw._on_validate_all()`.

Dvije posljedice koje v1.0 nije adresirala:

1. `processEvents()` znači da korisnik **može kliknuti drugu radnju usred
   pipeline-a** (npr. Izvezi XML). Nema nikakve brave.
2. „Postepeno pretvoriti faze u pozive `DeclarationWorkflowService`“ nije
   premještanje koda nego **inverzija zavisnosti** — servis ne smije zvati
   `fw._on_*` ni `QMessageBox`. To je znatno veći posao nego što v1.0 sugeriše.

### 3.5 Validacija se izvršava na UI threadu

`chat_intent_handler.py:800` `_tariff_usage_stats()` otvara PostgreSQL konekciju
i izvršava dva upita direktno iz `_prikazi_statistiku_tarife()` (linija 844) —
sinhrono, na UI threadu. Isti obrazac primijenjen na Fazu 3 (tarifni lookup +
decision status za svaku stavku fakture) daje sekunde zamrznutog prozora.

### 3.6 XML izvoz nema nijednu kapiju

`gui/tabs/agent/services/xml_workflow_service.py:264` `_izvezi_xml` — 23 linije:

- nikakva validacija prije `export_to_xml()`;
- otkazan `QFileDialog` (prazan `filepath`) i uspjeh se **ne razlikuju** — nema poruke;
- izuzetak ide samo u `chat.add_activity`, ne u `add_agent_message`;
- poruka je hardkodovana kao „Puna automatizacija završena!“ bez obzira na kontekst.

### 3.7 Osam konkurentnih „je li u redu“ reprezentacija

| Tip | Lokacija | Polje ishoda |
| --- | --- | --- |
| `ValidationResult` | `services/validation/validation_service.py:31` | `valid`, `has_blocking_errors()` |
| `ValidationResult` **(druga klasa, isto ime)** | `services/validation/preference_validator.py:19` | — |
| `ValidationItem` + `ValidationReport` | `services/agent/validation/declaration_validator_service.py:54,72` | `valid` |
| `Issue` + `ComplianceResult` | `services/agent/validation/declaration_validator_service.py:751,759` | — |
| `NaimenovanjeValidation` | `services/agent/validation/naimenovanja_review_service.py:25` | — |
| `PipelineStageResult` | `gui/tabs/agent/services/pipeline_stage_result.py` | `status`, `can_continue` |
| `ToolResult` | `services/agent/chat/tool_result.py` | `status`, `can_llm_infer` |
| `overall_outcome()` → `str` | `pipeline_stage_result.py` | `COMPLETED/PARTIAL/FAILED/CANCELLED` |

Uz to, ime `ValidationError` postoji na **pet mjesta** — jednom kao dataclass
(`validation_service.py:21`) i četiri puta kao izuzetak (`utils/exceptions.py:28`,
`importers/exceptions.py:116`, `services/core/exceptions.py:11`,
`services/core/base_service.py:32`).

> **Obaveza:** svaki adapter iz Faze 2 uvozi ove tipove **isključivo sa aliasom**
> (`from ... import ValidationResult as FakturaValidationResult`). Faza 0 pravi
> inventar kolizija.

---

## 4. Važeći izvori i njihov status

| Izvor | Status | Napomena |
| --- | --- | --- |
| `AGENTS.md` | kanonski | Jezik, arhitektura, GitNexus, testiranje i predaja |
| `docs/CONTEXT.md` | kanonski | Poslovna pravila i poznati bugovi — vidi mapiranje u §4.2 |
| `docs/decisions/001-tool-use-refactoring.md` | aktivan | Tool-first princip |
| `docs/decisions/002-tool-dispatcher-integration.md` | aktivan, nepotpun za V2 | Postojeća dispatcher integracija |
| `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` | djelimično realizovan | Faze A–D uglavnom završene |
| `docs/agent/AGENT_INTELLIGENCE_PLAN.md` | aktivan samo za tarifni scoring | Nije opšti plan chat inteligencije |
| `agent_reports/2026-07-19_plan-unapredjenja-agentskog-moda.md` | istorijski handoff | Status provjeriti kroz kod |
| `agent_reports/2026-07-20_faza-d-standardizovani-rezultati-observability.md` | aktivan | ToolResult, audit, idempotencija uvedeni |
| aktivni izvorni kod | **autoritativan** | U konfliktu kod + novija pravila imaju prioritet |

### 4.1 Već implementirani temelji — ne duplirati

- `services/agent/chat/tool_policy.py` — `ToolEffect.READ_ONLY|PROPOSE|MUTATE`,
  fail-closed whitelist (`TOOL_EFFECTS`, 12 alata).
- `services/agent/chat/tool_result.py` — `ToolResultStatus`, `ToolResult`,
  `render_tool_result_html`, `TOOL_RESULT_PROMPT_RULE`.
  **`ToolResult.can_llm_infer` već kodira pravilo iz §5.3** — ne pisati ga ponovo.
- `services/agent/chat/audit_log.py` — routing/provider/tool/pipeline audit.
- `services/decision/*` — `decision_policy.py`, `declaration_decision_service.py`,
  `evidence_adapters.py`, `integration.py`. **Jedini dozvoljeni izvor odluka**
  za tarifu, porijeklo i povlasticu.
- `services/agent/validation/declaration_validator_service.py` — završna
  validacija + spajanje sa `ComplianceCheckService`.
- `services/validation/validation_service.py` — Faktura/Naimenovanje validatori.
- `services/agent/validation/naimenovanja_review_service.py` — provjera popunjenosti.
- `gui/tabs/agent/workflow_state.py` — `WorkflowState` (8 UI stanja).
  **Nije poslovna spremnost deklaracije.**
- `gui/tabs/agent/services/pipeline_stage_result.py` — `PipelineStageResult`,
  `overall_outcome()`.
- `tests/unit/test_tool_policy.py` — **već postoji i tvrdi sinhronizaciju
  `TOOLS` ↔ `TOOL_EFFECTS`**. Svaka izmjena skupa alata mora proći kroz njega.
- `tests/unit/test_tool_result.py`, `tests/unit/test_audit_log.py`.

### 4.2 Poslovna pravila koja izvršilac NE smije re-derivirati

Umjesto ponovnog otkrivanja, koristiti direktno:

| Tema | `docs/CONTEXT.md` |
| --- | --- |
| `consumed_paths` i duplikati stavki | §1 |
| Historijski tarifni prijedlozi — samo isti izvoznik | §2 |
| Auto-popuni ne dira povlastice | §2 |
| Rb.31 strogo 3 linije + overflow marker | §3 |
| Rb.48 se ne kopira iz historijskog XML-a | §3 |
| Povlastica zahtijeva eksplicitnu potvrdu deklaranta | §4 |
| `itemChanged` + `blockSignals` | §5 |
| `MassCalculator`, per-invoice raspodjela | §6 |
| SQL — zabrana f-stringa | §7 |
| **Decision servis: `TariffMapping` nema `supplier` polje (poznat gap)** | §16 |
| GitNexus indeks degradiran za ovaj repo | §16 (2026-07-19) |

`docs/CONTEXT.md §16` direktno ograničava provjeru br. 11 u Fazi 3 — istorijska
razlika po dobavljaču se **ne može** dokazati iz `TariffMapping` dok gap postoji.

---

## 5. Scope lock i sigurnosne granice

### 5.1 Agent smije automatski

- čitati aktivni draft;
- prikazivati stanje;
- pokretati read-only validatore;
- računati mase kroz postojeći servis;
- normalizovati bezbjedne tehničke formate kada poslovna vrijednost ostaje ista;
- primijeniti tačno, ranije potvrđeno mapiranje samo kada `services/decision/`
  politika to eksplicitno dozvoli;
- kreirati strukturisan prijedlog;
- nastaviti workflow kada su sve prethodne kapije zadovoljene.

### 5.2 Agent ne smije automatski

- izmišljati tarifni broj, porijeklo, povlasticu ili dokument;
- tumačiti `UNKNOWN`/`NEEDS_REVIEW` kao potvrđen rezultat;
- upisati povlasticu bez eksplicitne potvrde deklaranta (`CONTEXT.md §4`);
- zaobići `DeclarationDecisionService`;
- grupisati naimenovanja van `CreateNaimenovanjaService.create_smart_group()`;
- nastaviti poslije blokirajuće validacione greške;
- izvesti XML bez završnog readiness rezultata i korisničke potvrde;
- tretirati warning kao uspjeh bez prikaza korisniku;
- koristiti LLM kao autoritet za poslovnu odluku;
- **pokrenuti drugu radnju dok je workflow aktivan** (single-flight, §7.6).

### 5.3 LLM u ciljnoj arhitekturi

Dozvoljeno: klasifikacija složenije namjere, sastavljanje plana iz whitelistanih
alata, jezičko formatiranje strukturisanih rezultata, objašnjavanje potvrđenih nalaza.

Zabranjeno: generisanje carinskih vrijednosti bez lokalnog dokaza, direktna
mutacija drafta, promjena severity/statusa koji je vratio servis, preskakanje kapija.

Mašinski izraz ovog pravila već postoji — `ToolResult.can_llm_infer` i
`TOOL_RESULT_PROMPT_RULE` u `tool_result.py`. Koristiti ih, ne pisati paralelno.

---

## 6. Ciljna arhitektura

```text
Korisnička poruka
    |
    v
Input Guard (check_injection)
    |
    v
Context Resolver          -- konkretan red / prethodni subjekt / pending potvrda
    |
    v
Intent Resolver           -- action | target | scope | depth | effect | goal
    |
    v
Plan Builder              -- 1 korak za prostu namjeru; N koraka za workflow cilj
    |
    v
Plan Validator            -- poznati alati | argumenti | ToolPolicy | preconditions | kapije
    |
    v
Tool Executor (worker thread) / Workflow Orchestrator (single-flight)
    |
    v
ToolResult / ValidationSummary / WorkflowRun
    |
    v
Deterministički renderer
    |
    v
Chat + audit + sljedeća dozvoljena akcija
```

### 6.1 Strogo razdvojene odgovornosti

| Komponenta | Odgovornost | Ne smije |
| --- | --- | --- |
| Context Resolver | Razrješava referencu na red, tab i prethodni subjekt | Birati poslovni zaključak |
| Intent Resolver | Razumije korisničku namjeru | Izvršavati alat |
| Plan Builder | Sastavlja listu koraka | Zaobići whitelist |
| Plan Validator | Provjerava dozvole i preconditions | Mutirati draft |
| Tool Executor | Poziva postojeće servise, u worker threadu | Izmišljati rezultat |
| Workflow Orchestrator | Vodi faze i pauze | Nastaviti kroz blokadu |
| Renderer | Prikazuje nalaze | Mijenjati status/severity |
| Audit | Bilježi tok | Rušiti korisničku operaciju |

---

## 7. Zajednički ugovori

### 7.1 `AgentIntent`

Lokacija: `services/agent/chat/intent_model.py`

```python
class IntentAction(str, Enum):
    SHOW = "show"
    VALIDATE = "validate"
    ANALYZE = "analyze"
    REQUEST_PROPOSAL = "request_proposal"   # namjera, NE ToolEffect.PROPOSE
    REQUEST_CHANGE = "request_change"       # namjera, NE ToolEffect.MUTATE
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
    scope: str = "all"                  # all | selection | row
    ordinals: tuple[int, ...] = ()
    depth: str = "summary"              # summary | full
    goal: str = ""
    confidence: float = 1.0
    source: str = "local"               # local | llm | context
    requires_clarification: bool = False
    clarification_reason: str = ""
```

> **Namjerno različita imena od `ToolEffect`.** v1.0 je koristila `MUTATE`/`PROPOSE`
> u oba enuma sa različitim značenjem (šta korisnik hoće vs. šta alat radi) — to
> je izvor tihih grešaka u `PlanValidator`-u. Mapiranje namjera → dozvoljeni efekat
> je eksplicitno:

| `IntentAction` | Dozvoljeni `ToolEffect` |
| --- | --- |
| `SHOW`, `VALIDATE`, `ANALYZE` | `READ_ONLY` |
| `REQUEST_PROPOSAL` | `READ_ONLY`, `PROPOSE` |
| `REQUEST_CHANGE` | `PROPOSE`, `MUTATE` (uz potvrdu) |
| `RUN_WORKFLOW`, `EXPORT` | prema koraku plana |

Pravila:

- `SHOW` nikada ne pokreće validator;
- `VALIDATE` nikada ne vraća samo snapshot;
- `REQUEST_CHANGE` uvijek prolazi `ToolPolicy`;
- `RUN_WORKFLOW` mora proizvesti validiran plan;
- `requires_clarification=True` samo kada dvije akcije imaju stvarno različite
  posljedice i kontekst ne razrješava namjeru.

### 7.2 `ValidationFinding` i katalog kodova

Lokacija: `services/agent/validation/finding_model.py`

```python
@dataclass(frozen=True)
class ValidationFinding:
    code: str
    target: str
    location: str
    message: str
    evidence: tuple[tuple[str, str], ...] = ()   # NE dict — vidi napomenu
    source: str = ""
    auto_fixable: bool = False
    suggested_action: str = ""
```

> **Zašto ne `evidence: dict`:** v1.0 je imala `frozen=True` sa `dict` poljem.
> Zamrznutost je tada iluzorna (dict se mijenja kroz referencu), a klasa je
> nehashable — pa se nalazi ne mogu deduplicirati kroz `set()`, što §20 traži.
> Tuple parova rješava oboje.

`severity` i `blocking` **nisu polja nalaza** — izvode se iz kataloga:

```text
services/agent/validation/finding_catalog.py
```

```python
FINDING_CATALOG: dict[str, FindingSpec] = {
    "MISSING_TARIFF": FindingSpec(severity="error", blocking=True, ...),
    "UNCONFIRMED_ORIGIN": FindingSpec(severity="warning", blocking=False, ...),
    ...
}
```

Jedan registar znači: adapteri ne odlučuju samostalno je li nešto blokada,
renderer ne parsira tekst, a testovi i metrike dijele isti izvor.

Minimalni skup kodova:

```text
MISSING_TARIFF              INVALID_TARIFF_FORMAT      TARIFF_NOT_FOUND
UNCONFIRMED_TARIFF          MISSING_ORIGIN             UNCONFIRMED_ORIGIN
UNCONFIRMED_PREFERENCE      PREFERENCE_WITHOUT_EVIDENCE
MISSING_AMOUNT              INVALID_QUANTITY           INVALID_WEIGHT
GROSS_LESS_THAN_NET         INVOICE_TOTAL_MISMATCH     WEIGHT_TOTAL_MISMATCH
DUPLICATE_INVOICE_LINE      MISSING_PACKAGE            INVALID_PROCEDURE
MISSING_STATISTICAL_VALUE   INVALID_RUB31              ITEM_GROUPING_MISMATCH
ASYCUDA_ITEM_LIMIT          HEADER_REQUIRED_FIELD      DOCUMENT_INCONSISTENCY
CROSS_TAB_MISMATCH          XML_PREFLIGHT_BLOCKED      CHECK_SKIPPED_SERVICE_DOWN
```

Posljednji kod je nov u odnosu na v1.0 i obavezan: bez njega „nije provjereno“
i „nema problema“ ostaju nerazlučivi, što je zahtjev iz §20.

### 7.3 `ValidationSummary`

```python
@dataclass
class ValidationSummary:
    target: str
    checked_count: int
    findings: list[ValidationFinding]
    checks_run: tuple[str, ...]
    checks_skipped: tuple[str, ...] = ()
    draft_revision: str = ""

    @property
    def blocking_count(self) -> int: ...
    @property
    def warning_count(self) -> int: ...
    @property
    def ready(self) -> bool:
        """Sve obavezne provjere izvrsene I nema blokada. NIJE 'nema praznih polja'."""
```

`blocking_count`/`warning_count`/`ready` su **izvedeni iz kataloga**, ne upisana
polja — upisano polje se može razići sa listom nalaza.

### 7.4 Plan gašenja starih reprezentacija ishoda

Uvođenje `ValidationSummary` je konsolidacija samo ako stari tipovi nestanu. Bez
ovog plana §3.7 postaje devet tipova umjesto osam.

| Tip | Sudbina | Kada |
| --- | --- | --- |
| `ValidationResult` (validation_service) | ostaje interno, izlaz samo kroz adapter | Faza 2 |
| `ValidationResult` (preference_validator) | **preimenovati** u `PreferenceValidationResult` | Faza 2 |
| `ValidationItem` / `ValidationReport` | ostaje interno, izlaz kroz adapter | Faza 2 |
| `Issue` / `ComplianceResult` | ostaje interno, izlaz kroz adapter | Faza 2 |
| `NaimenovanjeValidation` | ostaje interno, izlaz kroz adapter | Faza 2 |
| `PipelineStageResult` | ostaje — različit koncept (faza, ne nalaz) | — |
| `ToolResult` | ostaje — omotač alata; `data` nosi `ValidationSummary` | — |
| `overall_outcome()` → `"COMPLETED"` | mijenja se u `"READY_FOR_EXPORT"` | Faza 6 |

### 7.5 Poslovno stanje deklaracije — kapije, ne enum

Lokacija: `services/agent/workflow/declaration_gates.py`

v1.0 je predlagala enum od 16 stanja. Odbačeno: linearni enum poziva na to da se
stanje **upiše** negdje i postane drugi izvor istine koji se razilazi sa draftom.

Umjesto toga — nezavisne kapije, sve **izvedene iz drafta pri svakom pozivu**:

```python
@dataclass(frozen=True)
class Gate:
    id: str                      # "INVOICE_VALIDATED", "ORIGIN_CONFIRMED", ...
    satisfied: bool
    reason: str                  # zasto nije zadovoljena
    blocking_findings: tuple[str, ...]   # kodovi iz kataloga


def evaluate_gates(draft, *, services) -> tuple[Gate, ...]: ...
def current_stage(gates) -> str:
    """Prva nezadovoljena kapija. Izvedena vrijednost, nigdje se ne cuva."""
```

Kapije (redoslijed = redoslijed provjere):

```text
FILES_IMPORTED        INVOICE_PARSED        INVOICE_VALIDATED
TARIFFS_RESOLVED      ORIGIN_CONFIRMED      MASSES_CALCULATED
ITEMS_CREATED         ITEMS_VALIDATED       HEADER_READY
CROSS_CHECK_PASSED    XML_PREFLIGHT_PASSED
```

`READY_FOR_EXPORT` nije kapija nego zaključak: sve kapije zadovoljene.
`BLOCKED` nije stanje nego opis prve nezadovoljene kapije.

Time `Nastavi` (§18) postaje trivijalan: ponovo izračunaj kapije i nastavi od
prve nezadovoljene. Nema stale stanja jer se stanje ne čuva.

### 7.6 Izvršni ugovori — thread, brava, potvrda

Tri zahtjeva koje v1.0 nema, a bez kojih Faze 3–7 nisu isporučive:

**a) Van UI threada.** Svaki validacioni alat koji dodiruje bazu ili decision
servis izvršava se u `QThread` workeru i emituje progress. Referentni obrazac:
`ToolDispatcherWorker` (`tool_dispatcher.py:120`). Zabranjeno ponoviti obrazac
iz `_tariff_usage_stats` (§3.5).

**b) Single-flight brava.** Dok je workflow ili dugotrajni alat aktivan, nova
korisnička radnja se odbija sa jasnom porukom, ne stavlja u red. Razlog: §3.4 —
`processEvents()` propušta klikove.

```python
class AgentBusyError(RuntimeError): ...
# Orchestrator drzi jednu bravu; Plan Validator je provjerava kao precondition.
```

**c) Injektabilna potvrda.** `QMessageBox.question` se ne poziva iz servisa.

```python
ConfirmFn = Callable[[str, str], bool]   # (naslov, pitanje) -> bool
```

GUI prosljeđuje implementaciju sa `QMessageBox`; testovi prosljeđuju lambdu.
Bez ovoga kriterijum „rezultat se može testirati bez GUI dijaloga“ (§17) je
neispunjiv.

### 7.7 `AgentPlan` (koristi se u Fazi 7)

Lokacija: `services/agent/planning/agent_plan.py`

```python
@dataclass(frozen=True)
class PlanStep:
    id: str
    tool: str
    arguments: dict
    effect: ToolEffect
    preconditions: tuple[str, ...]      # ID-evi kapija iz §7.5
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

LLM rezultat nikada nije direktno izvršiv dok `PlanValidator` ne potvrdi alat,
argumente, effect i preconditions.

---

## 8. Skup alata — konsolidacija umjesto rasta

### 8.1 Problem

`TOOL_EFFECTS` danas ima 12 alata. Semantička matrica (§9) traži i:
`prikazi_fakturu`, `provjeri_fakturu`, `prikazi_faktura_stavku`,
`provjeri_naimenovanje` (jednina, ordinal), `provjeri_zaglavlje`,
`provjeri_uskladjenost_tabova`, `provjeri_spremnost_za_xml` — sedam novih, 19 ukupno.

Tačnost LLM izbora **opada** sa brojem sličnih alata, a §21 istovremeno traži
visoku tačnost. Devetnaest alata od kojih šest počinje sa `provjeri_` je loš dizajn.

### 8.2 Rješenje — dva parametrizovana alata

```text
prikazi(target, scope="all", ordinals=[])
provjeri(target, scope="all", ordinals=[], depth="summary")
```

`target` ∈ `application | invoice | tariffs | origin | items | header | declaration | cross_tab | xml`

Time skup pada sa 12 na 8 uz **veću** pokrivenost:

| Alat | Effect | Zamjenjuje |
| --- | --- | --- |
| `prikazi` | READ_ONLY | `pregled_stanja_aplikacije`, `prikazi_naimenovanja` |
| `provjeri` | READ_ONLY | `provjeri_tarife`, `provjeri_naimenovanja`, `validuj_deklaraciju` + 7 novih |
| `pretrazi_tarifu` | READ_ONLY | — |
| `pretrazi_porijeklo` | READ_ONLY | — |
| `pronadji_slicne_proizvode` | READ_ONLY | — |
| `analiziraj_tarifne` | READ_ONLY | — |
| `predlozi_tarife` | PROPOSE | — |
| `spoji_naimenovanja` | PROPOSE | — |
| `upisi_u_kolonu` | MUTATE | — |

`AgentIntent.action` + `.target` mapiraju se 1:1 na `prikazi`/`provjeri` —
resolver i alat govore isti jezik, što je i bila poenta Faze 1.

### 8.3 Obavezna pravila za imena i kompatibilnost

1. **Imena alata su ASCII**: `^[a-z0-9_]{1,64}$`. v1.0 je predlagala
   `provjeri_usklađenost_tabova` — Groq/OpenAI function-name shema odbija `đ`.
   Dodati test koji tvrdi ovo nad cijelim `TOOLS`.
2. Stara imena ostaju u `TOOL_EFFECTS` kao **aliasi** dok characterization testovi
   ne potvrde paritet; `is_known_tool()` ih i dalje prihvata.
3. `tests/unit/test_tool_policy.py` mora ostati zelen — on već tvrdi
   `TOOLS` ↔ `TOOL_EFFECTS` sinhronizaciju.
4. **SYSTEM_PROMPT se prepisuje** — pravila 6, 7 i 17 direktno uče pogrešno
   mapiranje (§3.2).

---

## 9. Semantika korisničkih komandi

| Primjer | AgentIntent | Alat |
| --- | --- | --- |
| `Prikaži Faktura tab` | SHOW / INVOICE | `prikazi(invoice)` |
| `Šta je učitano?` | SHOW / APPLICATION | `prikazi(application)` |
| `Provjeri Faktura tab` | VALIDATE / INVOICE | `provjeri(invoice)` |
| `Pregledaj tabelu Faktura` | VALIDATE / INVOICE / full | `provjeri(invoice, depth=full)` |
| `Pokaži stavku 17 iz fakture` | SHOW / INVOICE / row | `prikazi(invoice, scope=row, ordinals=[17])` |
| `Provjeri tarife` | VALIDATE / TARIFFS | `provjeri(tariffs)` |
| `Prikaži naimenovanja` | SHOW / ITEMS | `prikazi(items)` |
| `Pregledaj naimenovanja` | VALIDATE / ITEMS / full | `provjeri(items, depth=full)` |
| `Provjeri naimenovanje 5` | VALIDATE / ITEMS / row | `provjeri(items, scope=row, ordinals=[5])` |
| `Provjeri zaglavlje` | VALIDATE / HEADER | `provjeri(header)` |
| `Provjeri deklaraciju` | VALIDATE / DECLARATION | `provjeri(declaration)` |
| `Jesu li tabovi usklađeni?` | VALIDATE / DECLARATION | `provjeri(cross_tab)` |
| `Da li je spremno za XML?` | VALIDATE / XML | `provjeri(xml)` |
| `Nemoj mijenjati, samo pokaži` | SHOW / *kontekst* | `prikazi(...)` |
| `Pripremi deklaraciju` | RUN_WORKFLOW / DECLARATION | višekoračni plan (Faza 7) |
| `Nastavi` | RUN_WORKFLOW / current | prva nezadovoljena kapija |
| `Izvezi XML` | EXPORT / XML | readiness → potvrda → izvoz |

### 9.1 Jezičko pravilo

- `prikaži`, `pokaži`, `šta ima`, `šta je učitano` → prikaz;
- `provjeri`, `validiraj`, `da li je ispravno`, `šta fali` → validacija;
- `pregledaj` + poslovni objekat → **puna validacija**;
- `analiziraj` → dublje poređenje sa istorijom ili pravilima;
- `predloži` → nema automatskog upisa;
- `upiši`, `ispravi`, `primijeni` → mutacija sa ToolPolicy kapijom;
- `pripremi`, `završi`, `nastavi` → workflow namjera;
- **negacija** (`nemoj`, `bez izmjene`, `samo prikaži`) → obara akciju na `SHOW`
  bez obzira na ostatak rečenice. *Pravilo je nedostajalo u v1.0 iako §21 traži
  negacije u eval setu.*

---

## 10. Faza −1 — blokirajući preduslovi

> **STATUS: ZAVRŠENO (2026-07-26, commit `2b4e815`).** Sva četiri preduslova
> zatvorena — `draft.revision`/`fingerprint` (`core/draft/draft.py:474-489`,
> ALT pristup preko `bump_revision()` u `mark_dirty()`, ne `__setattr__`),
> `scripts/sync_dist_client.py`, `DEKLARANT_AGENT_V2` u `config/settings.py`
> (default `False`), inventar u
> `agent_reports/2026-07-26_faza-1d-inventar-kolizija-imena.md`. Detalji i
> obrazloženje ALT pristupa: `project_rooms/2026-07-26_faza-1a-draft-revision.md`.
> Testovi: `tests/unit/test_draft_revision.py` (8 testova). Sljedeći korak je
> **Faza 0** (dolje) — takođe već završena.

**Ovo je najvažnija izmjena u odnosu na v1.0.** Četiri stavke su bile skrivene
unutar kasnijih faza. Nijedna kasnija faza ne počinje dok ove nisu zatvorene.
Sve četiri su međusobno nezavisne i mogu ići paralelno.

### −1.A Revizija drafta (`draft.revision`)

`core/draft/` **nema** `revision`, `fingerprint` ni `__hash__` — provjereno.
Faza 6 (readiness sa fingerprintom) i §7.3 (`draft_revision` u summary) su bez
toga neisporučive.

- monotoni brojač ili stabilan hash sadržajnih polja;
- inkrementira se na svakoj izmjeni `invoice_lines`, `items`, zaglavlja;
- **nije** dio ASYCUDA XML izlaza;
- test: izmjena bilo kojeg polja mijenja reviziju; čitanje je ne mijenja.

Rizik: `DeclarationDraft` koriste svi tabovi i svi importeri.
**Obavezan `gitnexus_impact` prije izmjene; očekivano HIGH/CRITICAL → project room.**

### −1.B dist_client strategija

Svaki router fajl postoji dvaput (`services/agent/chat/tool_dispatcher.py` i
`dist_client/services/agent/chat/tool_dispatcher.py`, identični). V2 dodaje oko
osam novih modula i mijenja šest postojećih kroz sve faze.

Odluka mora pasti **sada**, ne u release fazi:

| Opcija | Trošak | Rizik |
| --- | --- | --- |
| Ručna sinhronizacija po fazi | nizak po fazi, visok ukupno | drift (već proizveo crash bug) |
| `scripts/sync_dist_client.py` + provjera u testovima | oko 1 dan | nizak |
| dist_client importuje iz root paketa | 2–3 dana | dira build (PyInstaller/Nuitka) |

Preporuka: **sync skripta + test koji pada na drift** za obuhvaćene putanje.
Pažnja: postoje `skip-worktree` fajlovi koji namjerno drže različit sadržaj —
sync skripta ih mora preskočiti.

### −1.C Kill-switch

Windows klijent (.55) je radna mašina. Cijeli V2 routing mora biti opoziv bez
novog builda:

```text
DEKLARANT_AGENT_V2=0|1   (.env, cita se kroz config/settings.py)
```

- `0` → `_handle_message` ide starim putem, bajt-identično;
- default u prvoj fazi je `0`, prebacuje se tek kad metrike iz §21 prođu;
- audit bilježi vrijednost zastavice uz svaki routing događaj.

### −1.D Inventar kolizija imena

Popisati sve klase iz §3.7 i njihove uvozne putanje; upisati u `agent_reports/`
i u zaglavlje `finding_model.py`. Bez ovoga adapteri iz Faze 2 uvoze pogrešan
`ValidationResult`/`ValidationError`.

**Procjena Faze −1:** 3–5 radnih dana.

---

## 11. Faza 0 — baseline i zaključavanje ponašanja

> **STATUS: ZAVRŠENO (2026-07-26, commiti `76c5a89`, `96a2911`).** Mapa svih 10
> routing slojeva sa dokazanim bugovima:
> `project_rooms/2026-07-26_faza0-agent-v2-baseline.md`. Fixture sa 50
> slučajeva (uklj. `reachable_branch` polje, dopunjeno u `96a2911`):
> `tests/fixtures/agent/intent_routing_cases.json`. Testovi:
> `tests/unit/test_agent_intent_routing_baseline.py` (50 passed, 28 skipped —
> Tool Use sloj mockovan). Napomena: fixture koristi polje `expected_sloj`
> umjesto `reachable_branch` iz originalnog primjera u ovom dokumentu — isto
> značenje, zadržati `expected_sloj` kao stvarni naziv polja u kodu, ne
> mijenjati radi usklađivanja sa ovim tekstom. Sljedeći korak je **Faza 1**
> (§12).

### Zadaci

1. Pročitati obavezne izvore iz §4 i §4.2.
2. `git status --short`; ne uključivati tuđe izmjene.
3. Provjeriti GitNexus svježinu (indeks je poznato degradiran — `CONTEXT.md §16`;
   dopuniti ručnim `rg` pregledom).
4. Mapa routing ulaza **sa dostižnošću** (ne samo popis):
   `_handle_message` → `_resolve_followup` → `_resolve_contextual_request` →
   `_application_context_scope` → naimenovanja regex → `route_local_tool` →
   LLM Tool Use → regex fallback → plain `ChatWorker`.
   Za svaku granu: koje poruke je stvarno dosežu, koje su zasjenjene.
5. Evidentirati mrtve grane (§3.3) — prijedlog: brisanje ili promjena redoslijeda.
6. Characterization testovi za potvrđene pogrešne i ispravne upite.
7. Sačuvati audit izlaz za najmanje 20 reprezentativnih komandi.

### Test fixture

```text
tests/fixtures/agent/intent_routing_cases.json
```

```json
{
  "message": "Provjeri tabelu u tabu Faktura",
  "expected_action": "validate",
  "expected_target": "invoice",
  "expected_tool": "provjeri",
  "expected_arguments": {"target": "invoice"},
  "must_not_call": ["prikazi"],
  "confirmation_required": false,
  "reachable_branch": "route_local_tool:71"
}
```

Polje `reachable_branch` je novo u odnosu na v1.0 i služi za dokazivanje §3.3.

### Kriterijumi prihvata

- svi routing slojevi dokumentovani **i označeni kao dostižni/mrtvi**;
- najmanje 50 početnih jezičkih slučajeva;
- poznate greške reproducibilne testom;
- **nema izmjene produkcionog ponašanja.**

**Procjena:** 2–3 radna dana.

---

## 12. Faza 1 — jedinstveni Intent Resolver

### Novi moduli

```text
services/agent/chat/intent_model.py
services/agent/chat/intent_resolver.py
services/agent/chat/intent_rules.py
```

### Obavezno izmijenjeni fajlovi

- `services/agent/chat/tool_definitions.py` — **primarni scope**, ne uzgredni
  (§3.2): SYSTEM_PROMPT pravila 6/7/17 i opisi `prikazi_naimenovanja`,
  `provjeri_naimenovanja`, `pregled_stanja_aplikacije`;
- `services/agent/chat/tool_policy.py` — novi `prikazi`/`provjeri` + aliasi;
- `services/agent/chat/tool_dispatcher.py` — `route_local_tool` se povlači u resolver;
- `gui/tabs/agent/services/chat_intent_handler.py` — `_handle_message`,
  `_application_context_scope`;
- `services/agent/chat/audit_log.py`;
- `tests/unit/test_tool_dispatcher.py`, `test_tool_policy.py`,
  `test_application_context_service.py`, `tests/test_origin_intent_routing.py`,
  `tests/unit/test_chat_context_followups.py`;
- novi `tests/unit/test_agent_intent_resolver.py`.

### Implementaciona pravila

1. Jedan resolver određuje action/target/scope prije dispatchera.
2. Lokalna pravila samo za visoko pouzdane, nedvosmislene obrasce.
3. LLM Tool Use tek za slučajeve koje pravila ne razriješe.
4. LLM vraća strukturisan intent ili tool call, ne slobodan poslovni zaključak.
5. Audit: action, target, confidence, `source` (`local|llm|context`), razlog
   fallbacka, **vrijednost kill-switcha**.
6. `_application_context_scope()` više ne smije presresti `VALIDATE`;
   redoslijed `faktura` prije `naimenov` (§3.3) se ispravlja.
7. `route_local_tool()` ne rutira svaku poruku sa `tab faktura` u snapshot.
8. Mrtve grane iz Faze 0 se brišu **u zasebnom commitu**, sa dokazom nedostižnosti.
9. Ne uklanjati stare grane dok characterization testovi ne potvrde paritet.
10. Compatibility adapter stari intent → `AgentIntent`.

### Kriterijumi prihvata

- `Prikaži Faktura tab` → snapshot;
- `Provjeri`/`Pregledaj Faktura tab` → validacija;
- `Prikaži naimenovanja` → pregled;
- `Provjeri`/`Pregledaj naimenovanja` → validacija;
- negacija (`samo prikaži`) obara na `SHOW`;
- konkretan red zadržava ispravnu ordinal logiku;
- **bez AI providera pouzdani lokalni slučajevi i dalje rade**;
- svaki intent fixture daje očekivani rezultat;
- nijedan `REQUEST_CHANGE` intent ne izvršava izmjenu;
- `DEKLARANT_AGENT_V2=0` vraća bajt-identično staro ponašanje.

### GitNexus prije izmjene

Obavezno: `_handle_message`, `_application_context_scope`, `route_local_tool`,
`ToolDispatcherWorker`, `_resolve_contextual_request`, `effect_for`.
HIGH/CRITICAL → project room + handoff upozorenje iz `AGENTS.md`.

**Procjena:** 4–6 radnih dana (v1.0: 3–5; povećano zbog `tool_definitions.py`
i konsolidacije alata).

---

## 13. Faza 2 — jedinstveni validacioni ugovor

### Pristup

Ne prepisivati postojeće validatore. Adapteri:

```text
services/agent/validation/finding_model.py
services/agent/validation/finding_catalog.py
services/agent/validation/invoice_validation_adapter.py
services/agent/validation/items_validation_adapter.py
services/agent/validation/header_validation_adapter.py
services/agent/validation/declaration_validation_adapter.py
```

Adapteri prevode osam tipova iz §3.7 u `ValidationFinding`. **Svaki uvoz sa
aliasom** prema inventaru iz Faze −1.D.

### Kriterijumi prihvata

- svaka validacija vraća stabilne kodove i lokacije;
- renderer ne parsira tekst poruke da bi odredio severity;
- severity/blocking dolaze **isključivo** iz `finding_catalog.py`;
- nema promjene poslovnih pravila samo zbog adaptacije;
- stari UI može koristiti compatibility renderer;
- testovi pokrivaju konverziju svakog starog tipa;
- `preference_validator.ValidationResult` preimenovan (§7.4);
- `ValidationFinding` je hashable (dedupe test).

**Procjena:** 3–5 radnih dana.

---

## 14. Faza 3 — stručna provjera Faktura taba

### Provjere

1. Popunjenost obaveznih polja.
2. Format tarifnog broja i sufiksa (8 interno / 10 u PG — `AGENTS.md`).
3. Postojanje tarife u zvaničnoj tarifi.
4. Status decision evidence za tarifu.
5. Zemlja porijekla i decision status.
6. Povlastica samo uz potvrđen dokaz (`CONTEXT.md §4`).
7. Iznos, količina i jedinica mjere.
8. Bruto/neto: nenegativno, bruto nije manje od neto, zbir po fakturi, kontrolna
   masa (bez zaokruživanja — `AGENTS.md`).
9. Duplikati i `consumed_paths` posljedice (`CONTEXT.md §1`).
10. Faktura/packing-list usklađenost kada oba izvora postoje.
11. Istorijske tarifne razlike — **ograničeno gapom iz `CONTEXT.md §16`**
    (`TariffMapping` nema `supplier`); ako se razlika ne može dokazati po
    dobavljaču, emitovati `CHECK_SKIPPED_SERVICE_DOWN`, ne prešutjeti.
12. Razdvajanje blokada, upozorenja i informacija.

### Tool ugovor

```text
provjeri(target="invoice", scope="all"|"selection"|"row", ordinals=[], depth="summary"|"full")
```

`ToolEffect.READ_ONLY`. Izvršava se u worker threadu sa progress signalom (§7.6.a).

### Očekivani odgovor

Zaključak → broj provjerenih stavki → kritične greške → upozorenja → šta nije
bilo moguće provjeriti → sljedeća akcija. Bez ispisa urednih redova.

### Kriterijumi prihvata

- provjerava **sve stavke drafta, bez ograničenja na prvih N**;
- prikazuje samo problematične redove i agregate urednih;
- `selection` scope poštuje selekciju;
- DB greška daje `CHECK_SKIPPED_SERVICE_DOWN`, nikad „nema problema“;
- rezultat identičan iz dugmeta i kroz agenta;
- **UI ostaje odzivan tokom provjere** (offscreen test mjeri da UI thread nije
  blokiran).

### Testovi

`tests/unit/test_agent_invoice_validation_tool.py`; proširiti postojeće Faktura
validacione testove; realne fakture iz `najavauvoza/` (**anonimizovane prije
commita** — presedan: 9 anonimizovanih slučajeva iz ranije Faze 7); DB
nedostupnost; 8/10-cifreni formati; bruto/neto edge cases; duplikovani
kombinovani import.

**Procjena:** 4–7 radnih dana.

---

## 15. Faza 4 — stručna provjera Naimenovanja taba

### Provjere

1. Sva obavezna polja Rb.31–46.
2. Interni osmocifreni format i odvojen sufiks.
3. Postojanje tarife.
4. Zemlja i povlastica uz potvrđen evidence.
5. Postupak i prethodni postupak.
6. Pakovanje, broj paketa i oznake (šifrarnik: PP je „Komad“, ne „Komadi“).
7. Bruto/neto po naimenovanju.
8. Vrijednost i statistička vrijednost.
9. Dopunska jedinica kada tarifa to zahtijeva.
10. Rub.31: izvor tarifnog opisa, trgovački nazivi, **280 znakova / 3 linije kroz
    stvarni builder** (`CONTEXT.md §3`), overflow marker.
11. Rub.40 i Rub.44 dokumenti.
12. Grupisanje po četiri ključa: tarifni broj, zemlja porijekla, povlastica, EUR.1 broj.
13. Limit 99 naimenovanja; upozorenje na 98/99.
14. Zbir masa i vrijednosti prema Faktura tabu.

### Važna granica

Validator **ne smije** implementirati vlastito grupisanje. Koristi isti
`GroupKey`/pravila kao `CreateNaimenovanjaService.create_smart_group()`
(`AGENTS.md` zabrana).

### Kriterijumi prihvata

- **sva naimenovanja iz drafta stvarno provjerena**;
- desetocifreni interni kod se prijavljuje;
- 98/99 daje upozorenje, 100 blokadu (`ASYCUDA_ITEM_LIMIT`);
- zbir i međutabne razlike vidljivi;
- uredni redovi agregirani, detalj jednog reda dostupan;
- **nema poruke „sve uredno“ ako je bilo koja provjera preskočena** —
  `checks_skipped` mora biti prikazan.

### Testovi

`tests/unit/test_agent_items_validation_tool.py`; Rub.31 real-builder test;
grupisanje po četiri ključa; 98/99/100 naimenovanja; zbir mase/vrijednosti;
nepotvrđena povlastica; desetocifreni kod.

**Procjena:** 4–7 radnih dana.

---

## 16. Faza 5 — Zaglavlje i međutabna usklađenost

### Provjere Zaglavlja

Tip deklaracije; izvoznik/primalac/deklarant; valuta, kurs i ukupan iznos
(CBBH kurs iz baze, ne hardkodovan); uslovi isporuke; transport i granična
ispostava; ukupna bruto/neto masa; broj paketa; Rb.40; priloženi dokumenti;
**Rb.48 se ne prepisuje iz istorijskog XML-a** (`CONTEXT.md §3`); template polja
samo kroz `TEMPLATE_FIELDS`.

### Međutabne provjere

Zbir Faktura iznosa = zbir naimenovanja; zbir kontrolnih masa = zbir
naimenovanja = zaglavlje; broj paketa; fakture u Rub.31/Rub.44; zemlje i
povlastice; dokumenti header/item; aktivni draft isti u sva tri taba; **nema
miješanja `draft.items` i `draft.invoice_lines`** (`AGENTS.md` zabrana).

### Alati

```text
provjeri(target="header")      # READ_ONLY
provjeri(target="cross_tab")   # READ_ONLY
```

ASCII imena (§8.3) — nema `usklađenost` u imenu alata.

### Kriterijumi prihvata

- razlikuje `missing` od `mismatch` (različiti kodovi);
- svaki mismatch navodi **obje vrijednosti i oba izvora**;
- automatski popunjena polja nisu tretirana kao korisnički potvrđena kada
  politika traži potvrdu;
- provjera **ne mijenja** Zaglavlje (test: revizija drafta nepromijenjena).

**Procjena:** 4–6 radnih dana.

---

## 17. Faza 6 — XML readiness i bezbjedan izvoz

### Novi servis

```text
services/agent/validation/xml_readiness_service.py
```

Orkestrira postojeće validatore i stvarni XML builder preflight. Ne duplira pravila.

### Kapije

Sve kapije iz §7.5, plus:

- XML builder gradi dokument **bez mutiranja produkcionog drafta**
  (preflight nad kopijom; test poredi reviziju prije/poslije);
- Rub.31 finalni format prolazi kroz stvarni builder;
- Rb.40/Rb.44 dokumenti prolaze.

### Tool ugovor

```text
provjeri(target="xml")
```

Vraća `READY` | `READY_WITH_WARNINGS` | `BLOCKED`, listu izvršenih i preskočenih
provjera, nalaze i **`draft_revision`** na kojem je provjera rađena.

### Zaštita od zastarjelog readiness rezultata

Readiness je vezan za `draft.revision` iz Faze −1.A. Ako se revizija promijeni
poslije preflighta, rezultat više ne važi — izvoz ga mora ponovo tražiti.

### XML izvoz

`_izvezi_xml` (`xml_workflow_service.py:264`) se prepisuje da:

1. pozove readiness;
2. odbije izvoz na `BLOCKED`;
3. prikaže upozorenja;
4. traži eksplicitnu završnu potvrdu kroz `ConfirmFn` (§7.6.c);
5. izveze XML;
6. **razlikuje otkazivanje od greške** (danas su nerazlučivi — §3.6);
7. auditira rezultat i putanju bez osjetljivog sadržaja.

Uz to: `overall_outcome()` se mijenja da vraća `READY_FOR_EXPORT` umjesto
`COMPLETED`, a `_finish_puna_auto_pipeline` da ne tvrdi završetak prije izvoza.

### Kriterijumi prihvata

- nije moguće izvesti blokiran draft kroz Agent tok;
- promjena revizije invalidira readiness;
- otkazivanje ne kreira fajl **i daje poruku**;
- greška buildera nije prikazana kao uspjeh;
- izvoz ne mijenja draft;
- rezultat testabilan bez GUI dijaloga.

**Procjena:** 5–8 radnih dana.

---

## 18. Faza 7 — Plan Builder i workflow

> **Obavezan scope — eksplicitna korisnička odluka (2026-07-26).** Cilj je jedna
> korisnička komanda („Pripremi deklaraciju“) koja pokreće cijeli proces do
> XML-a, uz obavezne pauze na kapijama za potvrdu deklaranta. Ova faza je zato
> core, ne uslovna kako je predloženo u v2.0. Odluka ne mijenja tehnički obim —
> inverzija zavisnosti iz `_puna_auto_pipeline` (§18 ispod) je i dalje najveći
> pojedinačni komad posla u cijelom planu i ne postaje lakša samo zato što je
> sada obavezna.

### Novi moduli

```text
services/agent/planning/agent_plan.py
services/agent/planning/plan_builder.py
services/agent/planning/plan_validator.py
services/agent/workflow/declaration_gates.py        (iz Faze −1/§7.5)
services/agent/workflow/declaration_workflow_service.py
```

### Kanonski workflow

```text
PREPARE_INPUT -> PARSE_AND_APPLY_IMPORT -> VALIDATE_INVOICE -> RESOLVE_TARIFFS
-> REVALIDATE_INVOICE -> REVIEW_ORIGIN_AND_PREFERENCE
-> WAIT_FOR_DECLARANT_CONFIRMATION -> CALCULATE_MASSES -> CREATE_ITEMS
-> VALIDATE_ITEMS -> PREPARE_HEADER -> VALIDATE_HEADER -> CROSS_CHECK
-> XML_PREFLIGHT -> READY_FOR_EXPORT -> WAIT_FOR_EXPORT_CONFIRMATION -> EXPORT
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

`Nastavi` = ponovo izračunaj kapije (§7.5) i nastavi od prve nezadovoljene.
Ne čuvati indeks koraka.

### Integracija sa postojećim pipeline-om — realan obim

v1.0 je ovo opisala kao „postepeno pretvoriti faze u pozive servisa“. To je
netačno: `_puna_auto_pipeline` zove `fw._on_calculate_masses()`,
`fw._on_auto_fill()`, `fw._on_validate_all()` i `QMessageBox` (§3.4). Potrebna je
**inverzija zavisnosti**:

1. izdvojiti poslovni dio iz `fw._on_*` metoda u servise (ostaje tanak GUI wrapper);
2. zamijeniti `QMessageBox` sa `ConfirmFn`;
3. ukloniti `QApplication.processEvents()` — pipeline ide u worker;
4. tek onda `DeclarationWorkflowService` može voditi faze.

Koraci 1–3 su realno **polovina obima ove faze**. Ne praviti drugi aktivni
pipeline paralelno.

### Kriterijumi prihvata

- jednostavan upit i dalje koristi jedan alat;
- složen cilj vraća vidljiv plan;
- korisnik vidi trenutnu kapiju i razlog pauze;
- workflow se može nastaviti;
- blokada se ne preskače porukom `nastavi`;
- svaki korak vraća strukturisan rezultat;
- **druga radnja tokom workflow-a je odbijena** (`AgentBusyError`, §7.6.b);
- pipeline završava na `READY_FOR_EXPORT`, ne na `COMPLETED`.

**Relativna složenost:** najveća u planu — vidi §25.3. Razlog je isključivo
inverzija zavisnosti (`fw._on_*` → servis, `QMessageBox` → `ConfirmFn`,
uklanjanje `processEvents()`), ne obim novog koda.

---

## 19. Faza 8 — nivoi automatizacije

> **Obavezan scope.** Definiše koje kapije ostaju ljudske bez obzira na režim —
> ovo je politika koja čini „jedna komanda do XML-a“ (Faza 7) bezbjednom, ne
> nezavisna funkcija. **Praktični cilj je Režim C** (§19 ispod) kao jedini
> aktivno korišćen tok: korisnik ukuca jednu komandu, agent vodi proces uz
> obavezne pauze na kapijama. Režimi A i B ostaju dizajnirani i pokriveni
> testovima (već su dio ugovora ispod), ali se ne grade kao korisnički vidljiv
> prekidač dok se izričito ne zatraži — to bi bio dodatni, nezatraženi obim.

### Režimi

- **A. Asistirani** — sve analize automatske, svaka mutacija traži potvrdu.
  Dizajniran i testiran; nije korisnički izložen u prvoj isporuci.
- **B. Kontrolisana automatizacija** — bezbjedne tehničke operacije automatske;
  decision politika odlučuje šta je dovoljno potvrđeno; carinski rizične
  vrijednosti i dalje traže potvrdu. Isto — dizajniran, nije prvi prioritet.
- **C. Priprema do XML-a** — workflow vodi proces; obavezne ljudske kapije ostaju;
  XML se ne izvozi bez završne potvrde. **Ovo je aktivni, isporučeni režim.**

### Obavezne ljudske kapije (u sva tri režima)

Nepouzdana ili konfliktna tarifa; porijeklo bez potvrđenog dokaza; PE1/PE2/PE3 i
EUR.1; povlastica; ozbiljan mismatch vrijednosti/mase; readiness upozorenje
označeno za obavezni review; finalni XML izvoz.

### Kriterijumi prihvata

- režim ne mijenja poslovnu validaciju;
- viši režim ne smanjuje sigurnosne kapije;
- audit bilježi režim;
- promjena režima je eksplicitna i vidljiva;
- testovi dokazuju **identičan blokirajući ishod u sva tri režima**.

**Relativna složenost:** mala — politika se nadovezuje na kapije koje Faza 7
već računa (§7.5); ovdje se samo definiše koje kapije ostaju ljudske po režimu.

---

## 20. Faza 9 — UX, objašnjivost i observability

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

- ne ispisivati uredne redove;
- prikazati problematične, grupisati iste nalaze (dedupe po `code`+`location` —
  zahtijeva hashable `ValidationFinding`, §7.2);
- `... i još N` samo kada korisnik ima način da otvori ostatak;
- jasno razlikovati: **nije pronađeno** / **nije provjereno** / **servis
  nedostupan** / **nema problema**;
- uz svaki nalaz prikazati izvor;
- akcija za odlazak na konkretan red.

### Observability

Audit događaj: session/workflow id, intent action/target, resolver source,
**vrijednost kill-switcha**, izabrani alat/plan, effect, provider, trajanje,
rezultat, broj nalaza po severity, razlog zaustavljanja, ishod potvrde,
`draft.revision` prije i poslije.

**Ne logovati** JIB, pune partner podatke, sadržaj dokumenata ni tajne.
Postojeći test privatnosti audita (`tests/unit/test_audit_log.py`) mora ostati zelen.

**Procjena:** 3–5 radnih dana. Može djelimično paralelno poslije Faze 2.

---

## 21. Faza 10 — evaluacija i release hardening

### 21.1 Intent evaluacija

Najmanje 150 rečenica: dijakritika i bez nje, tipfeleri, kratke komande,
konkretni redovi, follow-up poruke, **negacije**, prikaz vs provjera, provjera vs
mutacija, workflow ciljevi.

Metrike se mjere **odvojeno za dva puta** — v1.0 ih je miješala, pa je rezultat
zavisio od dnevnog ponašanja Groq/Gemini modela:

| Metrika | Rules-only (deterministički) | LLM fallback |
| --- | --- | --- |
| Action accuracy | **100%** na fixture setu | najmanje 90% |
| Target accuracy | **100%** | najmanje 93% |
| Opasna `REQUEST_CHANGE` klasifikacija | **100%** | **100%** |
| `SHOW`/`VALIDATE` konfuzija | **0%** | ispod 3% |

Nijedan poznati `VALIDATE` slučaj ne smije završiti snapshotom, ni u jednom putu.

### 21.2 Validaciona evaluacija

Realne fakture iz `najavauvoza/` (anonimizovane), poznati bug slučajevi iz
`agent_reports/`, 8/10-cifrene tarife, 98/99/100 naimenovanja, više faktura,
više zemalja, PE/EUR.1, kombinovani importeri, nedostupna baza, konfliktni
istorijski podaci.

### 21.3 Workflow E2E

Uredna deklaracija; nedostajuće tarife; konfliktna tarifa; nepotvrđeno porijeklo;
povlastica bez dokaza; neuspješan izračun masa; 100 naimenovanja; zaglavlje
mismatch; greška buildera; korisnik odbija potvrdu; resume poslije ručne
ispravke; **draft promijenjen poslije preflighta**; **paralelna radnja tokom
workflow-a**.

### 21.4 Test profili

```text
unit/offline           integration/local SQLite    integration/PostgreSQL
Qt offscreen           real-document regression    Windows build smoke
dist_client parity     UI-responsiveness (thread)  kill-switch OFF parity
```

Mock se ne koristi za SQLite/PostgreSQL poslovne testove (`AGENTS.md` zabrana).
LLM provider se smije mockovati u routing testovima.

### 21.5 Release kriterijumi

- ciljani testovi zeleni; puni suite bez novih regresija;
- **`DEKLARANT_AGENT_V2=0` daje ponašanje identično pre-V2 stanju**;
- DOC Guard prolazi;
- GitNexus `detect_changes` pregledan;
- dist_client sync test zelen;
- PyInstaller/Nuitka build smoke prolazi;
- ručni smoke na pravoj deklaraciji;
- XML diff provjeren prema očekivanom izlazu;
- nema automatske povlastice; nema izvoza blokiranog drafta.

**Procjena:** 7–10 radnih dana.

---

## 22. Paketi, redoslijed i test gate

| Paket | Faze | Uslov za predaju drugom agentu | Test gate |
| --- | --- | --- | --- |
| **P−1 Preduslovi** | −1 | nezavisan; 4 podzadatka paralelno | draft revision + dist sync + kill-switch |
| P0 Baseline | 0 | nema produkcionih izmjena | postojeći routing/tool testovi |
| P1 Intent | 1 | characterization fixture zaključan | intent fixture + dispatcher + follow-up + ASCII-name test |
| P2 Validation contract | 2 | P1 stabilan | adapter unit + stari validator testovi + dedupe |
| P3 Invoice review | 3 | P2 adapteri stabilni | faktura validation + realne fakture + UI responsiveness |
| P4 Items review | 4 | P2 stabilan | naimenovanja + Rub.31 + grupisanje + limit 99 |
| P5 Header/cross-check | 5 | P3 i P4 završeni | zaglavlje + zbirovi/cross-tab |
| P6 XML readiness | 6 | P5 završen | readiness + decision preflight + builder + invalidacija revizijom |
| P7 Planer/workflow | 7 | P6 (readiness) završen | pipeline stage + resume + failure/cancel + busy-lock |
| P8 Nivoi automatizacije | 8 | P7 završen | mutation gate + matrica potvrda |
| P9 UX/audit | 9 | djelimično paralelno poslije P2 | renderer + audit privacy |
| P10 E2E/release | 10 | sve prethodne | puni suite + Windows/dist smoke + kill-switch paritet |

P3 i P4 mogu paralelno **samo ako** oba izvršioca koriste zaključan
`ValidationFinding` + `finding_catalog` i ne diraju zajedničke router fajlove.

---

## 23. Obavezni GitNexus i git postupak

Prije svake izmjene:

1. pročitati `AGENTS.md` i `docs/CONTEXT.md` (posebno sekcije iz §4.2);
2. `git status --short`;
3. provjeriti indeks;
4. `gitnexus_impact(direction="upstream")` za svaki mijenjani simbol;
5. za HIGH/CRITICAL: `project_rooms/YYYY-MM-DD_kratak-naziv.md`, prijava rizika
   korisniku **prije** izmjene, scope lock, tip promjene i test gate;
6. dopuniti GitNexus ručnim `rg` pregledom pozivalaca — **indeks je poznato
   degradiran za ovaj repo** (`CONTEXT.md §16`; potvrđeno u ovoj analizi: indeks
   prijavljuje `services/agent/intent_classifier.py` koji ne postoji);
7. ne dirati nepovezane korisničke izmjene (`.worktrees/`, skip-worktree fajlovi).

Prije commita: ciljani testovi → `py_compile` → `gitnexus_detect_changes(scope="all")`
→ pregled procesa → DOC Guard → stage po logičkim cjelinama → commit bez
`--no-verify` → agent report → `docs/CONTEXT.md` samo za ne-očigledne trajne
odluke → provjera GitNexus stale statusa.

---

## 24. Definition of Done za Agent V2

- prikaz, validacija, analiza, prijedlog, mutacija i workflow jasno razdvojeni;
- potvrđeni routing skup prolazi metrike iz §21.1, **odvojeno po putu**;
- Faktura, Naimenovanja i Zaglavlje imaju autoritativne read-only provjere;
- postoji međutabna provjera;
- postoji jedan readiness rezultat za XML, vezan za `draft.revision`;
- readiness se invalidira poslije izmjene drafta;
- validacija ne blokira UI thread;
- agent odbija paralelnu radnju umjesto da je tiho izvrši;
- agent ne izmišlja carinske vrijednosti;
- mutacije prolaze `ToolPolicy` i `services/decision/`;
- povlastica uvijek pod eksplicitnom potvrdom;
- XML se ne izvozi bez readiness provjere i završne potvrde;
- otkazivanje i greška su razlučivi;
- audit omogućava rekonstrukciju odluke bez curenja osjetljivih podataka;
- `DEKLARANT_AGENT_V2=0` vraća staro ponašanje bez novog builda;
- dist_client nije u driftu;
- realni dokumenti i Windows smoke testovi prolaze;
- nijedan postojeći ispravan ručni workflow nije pokvaren;
- **jedna korisnička komanda pokreće cijeli proces do XML-a** (Režim C, §19) i
  zaustavlja se tačno na kapijama iz §7.5, ne prije i ne poslije;
- `Nastavi` nastavlja od prve nezadovoljene kapije bez preskakanja blokade.

---

## 25. Procjena obima

### 25.1 Šta ove brojke jesu i šta nisu

v2.0 je izražavala obim u „radnim danima“ po fazi, računato kao da jedan
developer piše kod ručno. To je pogrešan model. Ovaj plan realizuju AI agenti —
najmanje dva, paralelno gdje god zavisnosti to dozvoljavaju (§22, kolona „Uslov
za predaju“) — a pisanje koda, testova i pokretanje `pytest`/`py_compile` traje
minute, ne dane. Zato su brojke ispod preformulisane kao **relativna
implementaciona složenost** (§25.3), ne kalendarski raspored.

Stvarno ograničenje wall-clock vremena nije brzina pisanja koda, nego:

1. **Kritični put** — sekvencijalni lanac faza koje moraju ići jedna za drugom
   bez obzira koliko agenata radi (§25.2);
2. **Test gate po paketu** — svaki paket iz §22 mora proći svoj test gate prije
   nego što sljedeći počne; ovo je sekvencijalno, ali brzo (minute);
3. **Obavezan pregled na HIGH/CRITICAL nalazima** — `draft.revision` (Faza −1.A),
   prepravka `tool_definitions.py` (Faza 1) i inverzija zavisnosti u
   `_puna_auto_pipeline` (Faza 7) će vjerovatno vratiti HIGH/CRITICAL
   `gitnexus_impact` i po `AGENTS.md` traže tvoju potvrdu prije nastavka — to je
   stvarna pauza koju ni broj agenata ni njihova brzina ne skraćuju;
4. **Tvoj dnevni token/poruka budžet** — po tvojoj vlastitoj procjeni ovo je
   realno najveće ograničenje, potpuno nezavisno od složenosti koda.

### 25.2 Kritični put

Minimalan broj sekvencijalnih koraka, bez obzira koliko agenata radi paralelno
— svaki sljedeći zavisi od test gate-a prethodnog:

```text
Faza −1 (4 podzadatka paralelno)
   -> Faza 0
   -> Faza 1
   -> Faza 2
   -> max(Faza 3, Faza 4)      -- paralelno, vidi napomenu ispod tabele §22
   -> Faza 5
   -> Faza 6
   -> Faza 7
   -> Faza 8
   -> Faza 10                  -- Faza 9 djelimično paralelno poslije Faze 2
```

Deset sekvencijalnih koraka. Sa dva ili više agenata koji rade kontinuirano i
brzim test/review ciklusom, ovo je realno **posao od 2–3 dana rada**, pod
uslovom da:

- pregled na HIGH/CRITICAL kapijama (stavka 3 iznad) ne čeka dugo;
- dnevni token/poruka budžet dozvoljava da se u istoj sesiji zatvori barem
  nekoliko faza.

Ako se dnevni limit potroši usred faze, kritični put se jednostavno nastavlja
sljedećeg dana od tačke gdje je stao — plan ne zavisi od proteklog vremena,
nego od toga da je test gate prethodne faze zelen prije početka sljedeće.
Realan raspon je zato **2–3 dana rada u optimalnom slučaju, do nekoliko dana
duže ako dnevni budžet često prekida sesiju usred faze** — to drugo nije rizik
plana, nego posljedica tvog dostupnog budžeta, van kontrole ovog dokumenta.

### 25.3 Relativna složenost po fazi

Ne raspored, nego vodič gdje je više posla — koristan za raspodjelu između
paralelnih agenata:

| Faza | Složenost | Zašto |
| --- | --- | --- |
| −1 | S (4 nezavisna komada) | Svaki podzadatak mali; paralelizacija trivijalna |
| 0 | S | Uglavnom čitanje i mapiranje, bez izmjene koda |
| 1 | M | `tool_definitions.py` + resolver + konsolidacija alata 12→8 |
| 2 | M | Adapteri za 8 postojećih tipova, bez nove poslovne logike |
| 3 | M | Provjera fakture — najviše poslovnih pravila po stavci |
| 4 | M | Provjera naimenovanja — grupisanje + Rub.31 real-builder test |
| 5 | S–M | Zaglavlje + cross-tab, nadovezuje se na 3/4 |
| 6 | M | Readiness servis + revision-invalidacija |
| 7 | **L** | Inverzija zavisnosti u `_puna_auto_pipeline` — najveći pojedinačni komad u planu |
| 8 | S | Politika kapija preko servisa koji Faza 7 već računa |
| 9 | S | Renderer + audit, djelimično paralelno sa 2+ |
| 10 | M | E2E scenariji + Windows/dist smoke — traje zbog stvarnog build/test vremena, ne pisanja koda |

**Napomena o Fazi 7 (L):** jedina faza gdje je realna složenost suštinska
(inverzija zavisnosti — `fw._on_*` u servis, `QMessageBox` u `ConfirmFn`,
uklanjanje `processEvents()`), ne obim novog koda. Čak i sa 2+ agenta paralelno,
unutar same Faze 7 koraci 1→2→3→4 (§18) ostaju sekvencijalni jedan na drugom.

---

## 26. Prvi konkretan implementacioni zadatak

> **Faza −1 i Faza 0 su ZAVRŠENE** (2026-07-26, commiti `2b4e815`, `76c5a89`,
> `96a2911` — vidi status-blokove u §10 i §11). Sljedeći zadatak je **Faza 1**.

> Implementirati **Fazu 1** — `AgentIntent` model, `intent_resolver.py`,
> obavezna prepravka `tool_definitions.py` (SYSTEM_PROMPT pravila 6/7/17 i opisi
> `prikazi_naimenovanja`/`provjeri_naimenovanja`/`pregled_stanja_aplikacije` —
> §3.2), konsolidacija alata 12 → 8 (§8). Koristiti postojeći
> `tests/fixtures/agent/intent_routing_cases.json` (50 slučajeva, polje
> `expected_sloj`) kao characterization baseline — ne praviti novi fixture.

Scope lock:

- ne mijenjati nijednu poslovnu validaciju;
- ne mijenjati carinsku logiku ni decision policy;
- ne dodavati automatske mutacije;
- mrtve grane iz `project_rooms/2026-07-26_faza0-agent-v2-baseline.md` (§2.1,
  §2.3) se brišu tek pošto characterization testovi potvrde paritet, u
  zasebnom commitu (§12 implementaciono pravilo 8).

Obavezni izlaz:

- `services/agent/chat/intent_model.py`, `intent_resolver.py`, `intent_rules.py`;
- prepisan `tool_definitions.py` (SYSTEM_PROMPT + opisi alata);
- `prikazi`/`provjeri` u `tool_policy.py`, stara imena kao aliasi;
- `DEKLARANT_AGENT_V2=0` daje bajt-identično staro ponašanje (test);
- svi postojeći 50 fixture slučajeva prolaze sa novim resolverom;
- jasna migraciona tačka za Fazu 2.
