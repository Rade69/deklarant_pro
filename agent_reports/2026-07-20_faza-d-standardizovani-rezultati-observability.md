# Agent Report — 2026-07-20: Faza D — standardizovani rezultati i observability

## Datum
2026-07-20

## Agent
Claude Sonnet 5

## Scope
- `services/agent/chat/tool_result.py` + dist_client
- `services/agent/chat/audit_log.py` (novo) + dist_client
- `services/agent/chat/tool_dispatcher.py` + dist_client
- `gui/tabs/agent/services/chat_intent_handler.py` + dist_client
- `gui/tabs/agent/services/import_pipeline_service.py` + dist_client
- `services/agent/llm_audit_log.py` + dist_client
- `services/agent/tariff/tariff_rag_service.py` + dist_client
- `services/agent/tariff/tariff_suggestion_service.py` + dist_client
- `gui/tabs/agent/agent_controller.py` + dist_client
- `gui/tabs/agent/widgets/chat_worker.py` + dist_client
- `tests/unit/test_tool_result.py`, `test_audit_log.py` (novo), `test_tool_dispatcher.py`,
  `test_agent_mutation_gate.py`
- `project_rooms/2026-07-20_faza-d-standardizovani-rezultati-audit.md`

Realizovana **Faza D** iz `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` §8.
Faze E–F nisu rađene. Paralelno je na grani `feature/draft-autosave-nacrt` (Pi agent)
rađen zaseban, nezavisan zadatak (autosave nacrta) — bez preklapanja fajlova.

---

## Status izvora

- Plan (dograđen §5.6/§6.6/§7.7/§10.4 istom sesijom ranije) — aktivan, jedini izvor za §8.
- `agent_reports/2026-07-19_faza-a-*.md` — aktivan; ovaj prolaz zatvara poznat gap
  iz Faze A (`operation_id` idempotencija, dokumentovan kao `xfail` sa jasnim
  objašnjenjem u `test_agent_mutation_gate.py`).
- `agent_reports/2026-07-19_faza-b-*.md` — aktivan; ovaj prolaz je usput ispravio
  2 zastarjele DeepSeek reference u komentarima/docstringovima koje Faza B nije
  pokrila (`tool_dispatcher.py` docstring, `chat_intent_handler.py::_on_error`
  mrtva provjera greške koja se od uklanjanja DeepSeek-a nikad nije mogla desiti).

---

## GitNexus impact

Prije izmjene: `ToolResult` (LOW, 12 impacted, 4 direktna), `ToolDispatcherWorker`
(LOW, 8 impacted, 2 direktna) — provjereno prije početka rada.

**Nakon svih izmjena i commitova**: `gitnexus_detect_changes(scope="all")` →
**risk_level: CRITICAL**, 141 promijenjenih simbola, 21 fajl, 36 affected_processes.

Detaljna analiza (puna verzija u `project_rooms/2026-07-20_faza-d-standardizovani-rezultati-audit.md`):
CRITICAL oznaka je artefakt **obima** (9 produkcijskih fajlova u jednom prolazu —
tačno ono što plan §8 traži) i GitNexus fan-out brojanja kroz visoko-centralne
funkcije (`ChatWorker.run`, `_pg_today_stats`), NE dokaz krhke izmjene:

- 5 od 9 fajlova (`llm_audit_log.py`, `tariff_rag_service.py`,
  `tariff_suggestion_service.py`, `agent_controller.py`, `chat_worker.py`) —
  **isključivo** `print()` → `logger` konverzija unutar `except` blokova. Provjereno
  liniju-po-liniju: nijedna izmjena ne dira return vrijednost, argument, kontrolni
  tok ili emitovan Qt signal.
- Jedina promjena **oblika** postojećeg ugovora: `ToolDispatcherWorker` signali
  (`tool_call_received`, `fallback_to_chat`) dobili dodatni `provider` parametar.
  `grep` kroz cio repo (root+dist_client+testovi) potvrđuje tačno jedno mjesto
  koje se povezuje na te signale — već ažurirano konzistentno.

---

## Šta je urađeno

### 1. `ToolResult` — dodana polja za uspješne rezultate (plan §8.1)

Dodano: `effect: Optional[ToolEffect]`, `confirmation_required: bool`,
`operation_id: str`, i `ToolResult.ok()` klasa metoda (do sada su postojale samo
`needs_review`/`unknown`/`error` — uspješan rezultat nije imao strukturisan oblik).

### 2. `audit_log.py` (novi modul) — strukturisan audit (plan §8.2)

`AuditEvent` dataclass (routing_layer, tool, effect, status, source, provider,
duration_ms, fallback_reason, confirmation, pipeline_stage, extra) + `record()`
koja piše kroz standardni `logging` (logger `deklarant_pro.agent.audit`) i **nikad
ne baca** — greška u audit sloju je uhvaćena i tiho ignorisana, ne smije srušiti
korisničku operaciju (plan §8.3 kriterijum).

Namjerno **nije** dodata nova baza/tabela — plan §8.2 traži strukturisan zapis, a
postojeći `services/agent/llm_audit_log.py` (PostgreSQL/SQLite tabela) je zaseban,
uži koncept (samo token budžet), dijeljen sa svim klijentima preko PostgreSQL šeme
— proširivanje TE tabele novim kolonama bilo bi shema-migracija na dijeljenoj
infrastrukturi, van scope-a i rizika ove faze. `logging`-bazirano rješenje trivijalno
zadovoljava "audit pad ne ruši operaciju" (logging skoro nikad ne baca).

### 3. Audit svih routing slojeva (`chat_intent_handler.py`)

`_handle_message` sad bilježi koji routing sloj je obradio poruku na SVAKOJ grani:
`contextual` (`_resolve_contextual_request`), `local` (7 kraćih grana — followup,
pregled stanja, naimenovanja review, porijeklo, pending action confirm/reject,
slični proizvodi), `tool_use` (dispatch/fallback/error), `regex_fallback`, `plain_chat`.
Instrumentacija je na **poziv-mjestu** (jedan red prije svakog postojećeg `return`),
ne unutar internih funkcija — `_resolve_contextual_request` ima 10+ internih
`return True` tačaka, dirati svaku bi bio nepotreban i rizičniji zahvat.

`_execute_tool` omotan audit logikom: mjeri trajanje, hvata izuzetak SAMO da
zabilježi audit prije `raise` (ponašanje greške nepromijenjeno — i dalje propagira
identično kao prije). `effect` polje dodano na sve emitovane `ToolResult` objekte
unutar `_dispatch_known_tool` (needs_review/unknown grane).

### 4. Zatvoren operation_id gap iz Faze A (plan §16)

`_propose_kolona_upis` dodjeljuje `operation_id = uuid.uuid4().hex`.
`_on_proposal_confirmed`/`_on_proposal_rejected` ga **atomarno konzumiraju**
(provjera `hasattr` + `del`, isti provjereno-ispravan obrazac kao postojeći
`_pending_kolona_tab`) PRIJE bilo kakvog izvršenja. Drugi/repliciran signal na
istoj proposal kartici je sad no-op umjesto dvostrukog upisa.

`tests/unit/test_agent_mutation_gate.py::test_dvostruka_potvrda_ne_izvrsava_mutaciju_dvaput`
je do sada bio `xfail(strict=True)` sa eksplicitnim objašnjenjem ovog tačnog gap-a
— marker uklonjen, test sad genuinski prolazi.

### 5. Provider info kroz Tool Use lanac (`tool_dispatcher.py`)

`DispatchResult.provider` ("local"/"groq"/"gemini"/"") + Qt signali prošireni da
nose provider do `chat_intent_handler.py` — omogućava audit da zabilježi koji je
provider stvarno odgovorio (ili "local" za lokalni keyword router koji zaobilazi LLM).

### 6. Pipeline audit (`import_pipeline_service.py`)

`_finish_puna_auto_pipeline` (jedina centralna tačka, poziva se na svakom
early-exit i na kraju) bilježi jedan audit dogadjaj po fazi (`pipeline_stage` +
`status`) — bez diranja bilo kojeg od 13 mjesta gdje se `PipelineStageResult`
kreira (nizak rizik, centralizovano).

### 7. print() → logger (5 fajlova, plan §8.2)

Svi aktivni `print()` pozivi u runtime agent toku (izvan `if __name__ == "__main__":`)
zamijenjeni `logger.debug/warning/error`. CLI/test pomoćni ispisi u
`exporter_xml_indexer.py`/`supplier_profiling_service.py` (oba unutar `__main__`
guard-a) namjerno netaknuti — plan §8.2 eksplicitan izuzetak.

### 8. Usput ispravljeno: stale DeepSeek reference (definition-of-done stavka)

- `tool_dispatcher.py::run()` docstring "Pošalji poruku DeepSeek-u" → ispravljeno
  (kod od Faze B stvarno zove `LLMProvider.complete_with_tools()`, Groq→Gemini).
- `chat_intent_handler.py::_on_error` — provjera `"deepseek api ključ nije podešen"
  in err_l` je bila **mrtav kod** (ta poruka grešaka se od Faze B nikad ne može
  desiti, jer DeepSeek više ne postoji u `LLMProvider`-u). Zamijenjena tačnom
  provjerom stvarne poruke greške (`"nema dostupnog ai providera"`, koju
  `tool_dispatcher.py::_dispatch` zaista vraća kad ni Groq ni Gemini nisu podešeni).

---

## Zašto je urađeno

Plan §8 traži da svaki tool odgovor pokazuje izvor/status (ne samo greške), i da
se sistemski bilježi koji routing sloj/provider je obradio poruku — bez toga je
nemoguće odgovoriti na pitanja poput "koliko često Tool Use stvarno uspije vs.
pada na regex fallback" ili "koji provider zapravo nosi najveći dio saobraćaja".
`operation_id` fix direktno zatvara rizik naveden u plan §16 (dupli signal =
dvostruko izvršenje mutacije) koji je Faza A namjerno ostavila kao dokumentovan,
poznat gap.

---

## Kako je urađeno

Minimalno-invazivan pristup svuda gdje je bilo moguće: audit pozivi dodati na
POSTOJEĆIM granama/povratnim tačkama (jedan red), ne restrukturiranjem funkcija.
Jedino strukturno izdvajanje: `_execute_tool` je podijeljen na tanak omotač
(gate + audit + try/except) i `_dispatch_known_tool` (originalni elif lanac,
nepromijenjen) — radi čistog mjesta za mjerenje trajanja bez guranja audit logike
u svaku pojedinačnu granu.

---

## Šta nije dirano

- `gui/tabs/faktura_view.py`, `gui/tabs/naimenovanja_view.py` — netaknuti (Faza C
  teritorija, van scope-a).
- `services/decision/*` — netaknuto.
- Interna poslovna logika tarifnog/porijeklo/hybrid matchinga u sve 3 tariff/
  suggestion datoteke — netaknuta, samo dijagnostika u `except` blokovima.
- `services/agent/llm_audit_log.py` DB šema — namjerno nije proširena (vidi
  "Šta je urađeno" #2, obrazloženje).
- `_confirm_safe_to_exit()` / `_resolve_contextual_request()` interna logika —
  netaknuta.
- Faze E (integracioni testovi prije refaktora), F (razlaganje
  `ChatIntentHandler`-a) — čekaju odluku korisnika.

---

## Verifikacija

```
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
→ 803 passed, 58 skipped, 4 failed (sve pretpostojeće/okolinske - vidi "Pronađeni
  problemi"), 1 error (test_model_benchmark.py, pretpostojeći fixture gap,
  nepovezano)

python -m py_compile <11 izmijenjenih/novih fajlova, root i dist_client, 22 putanje>
→ OK

diff (bez BOM) root/dist_client za svih 10 fajlova → IDENTIČNI

grep tool_call_received/fallback_to_chat .connect/.emit u cijelom repou
→ tačno 2 mjesta, oba ažurirana konzistentno

mcp__gitnexus__detect_changes(scope="all") nakon commitova
→ risk_level: critical (analiza u project_rooms/2026-07-20_faza-d-*.md —
  artefakt obima, ne krhke izmjene, vidi "GitNexus impact" gore)
```

---

## Pronađeni problemi

- 4 test faila u punom run-u su **pretpostojeći, nepovezani**:
  - `test_pdf_plumber_only.py::test_tabula_not_in_smart_pdf` — `UnicodeDecodeError`
    (cp1252 čitanje fajla), okolinski problem ove mašine/konzole.
  - `test_xml_parser_fix.py::test_xml_parser` — hardkodovana putanja
    `/home/radovan/Documents/Računi/1.xml` koja ne postoji na ovoj mašini.
  - `test_tariff_validation_dialog.py` x2 — ista, već dokumentovana Pi/Codex
    regresija iz commita `7eb31fd` (2026-07-18), pominjana u Faza B izvještaju.
  - `test_model_benchmark.py::test_model` — nedostaje pytest fixture
    `model_name` (konfiguracijski gap, ne povezano sa agent kodom).
- Nijedan od ova 4 problema nije diran niti uzrokovan ovom fazom — potvrđeno
  `git log`/`git diff` da su fajlovi netaknuti ovom sesijom.

---

## Konflikti / kontradiktorni izvori

Nema. Plan §8 je bio dovoljno jasan; jedina odluka koju sam donio bez eksplicitnog
plan-teksta je da audit bude `logging`-baziran umjesto nove DB tabele — obrazloženo
gore ("Šta je urađeno" #2), niskog je rizika i reverzibilno (lako se kasnije doda
perzistentni sink ako zatreba).

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `c34c8b1` | feat(agent): prosiri ToolResult i dodaj audit_log (Faza D) |
| `8561c4f` | refactor(agent): audit svih routing slojeva + operation_id idempotencija |
| `bb95cd6` | refactor(agent): zamijeni print() loggerom u runtime agent toku |
| `0848936` | test(agent): pokrij ToolResult.ok, audit_log, operation_id idempotenciju |
| `02707da` | docs(project): project_room analiza CRITICAL GitNexus impact - Faza D |

---

## Tabela alata i konačan ToolEffect (plan §18, obavezno za Fazu D)

| Alat | ToolEffect | Zahtijeva potvrdu? |
|------|------------|---------------------|
| `predlozi_tarife` | PROPOSE | Ne (prikazuje prijedlog, ne upisuje sam) |
| `pregled_stanja_aplikacije` | READ_ONLY | Ne |
| `provjeri_tarife` | READ_ONLY | Ne |
| `pretrazi_tarifu` | READ_ONLY | Ne |
| `pretrazi_porijeklo` | READ_ONLY | Ne |
| `validuj_deklaraciju` | READ_ONLY | Ne |
| `prikazi_naimenovanja` | READ_ONLY | Ne |
| `provjeri_naimenovanja` | READ_ONLY | Ne |
| `upisi_u_kolonu` | **MUTATE** | **DA — proposal kartica + operation_id (Faza D fix)** |
| `spoji_naimenovanja` | PROPOSE | Ne (prikazuje prijedlog spajanja) |
| `analiziraj_tarifne` | READ_ONLY | Ne |
| `pronadji_slicne_proizvode` | READ_ONLY | Ne |

Nepromijenjeno od Faze A — ova faza nije mijenjala klasifikaciju, samo je zatvorila
idempotencijski gap za jedini MUTATE alat.

## Lista mutacija koje sada zahtijevaju potvrdu (plan §18)

Jedina mutacija u sistemu je `upisi_u_kolonu` (preko oba puta — Tool Use i regex
fallback, isti `_propose_kolona_upis` mehanizam). Od ove faze: potvrda je i
**idempotentna** (operation_id se konzumira tačno jednom).

## Konačan provider redoslijed (plan §18)

Nepromijenjeno od Faze B: **Groq → Gemini** (DeepSeek/OpenRouter trajno uklonjeni).
Ova faza dodaje samo vidljivost (audit) koji provider je stvarno odgovorio na
svaki poziv — ne mijenja sam redoslijed/fallback logiku.

---

## Rizici / ograničenja

- Audit log (`services/agent/chat/audit_log.py`) piše kroz standardni `logging` —
  nema perzistentnog upita/dashboard-a nad njim u ovoj fazi (plan to i ne traži
  za Fazu D, samo strukturisan zapis). Ako zatreba agregacija/upit, treba
  poseban zadatak (npr. log shipping ili DB sink).
- `_handle_message`-ovih 7 "local" grana dijeli isti `tool=` naziv granularnost
  (npr. "followup", "pregled_stanja_aplikacije") — nije 1:1 sa ToolPolicy imenima
  za grane koje nisu prošle kroz `_execute_tool` (očekivano, te grane nisu LLM
  tool pozivi nego direktni keyword prepoznavanje).
- Nije rađen live test protiv pravog Groq/Gemini API-ja u ovoj sesiji (mock-based
  unit testovi, isti pristup kao Faza A/B/C).

---

## Potreban follow-up

- Faze E (integracioni testovi prije refaktora), F (razlaganje
  `ChatIntentHandler`-a) čekaju odluku korisnika o nastavku.
- Grana `feature/draft-autosave-nacrt` (Pi agent, zaseban paralelan zadatak) i
  dalje čeka merge u `windows` — nezavisno od ove faze.

---

## Potrebna korisnička potvrda

- Ručno testirati u pravoj aplikaciji: potvrditi da dvoklik/brz dupli klik na
  proposal karticu (npr. simuliran preko dva brza poziva) ne upisuje vrijednost
  dvaput (automatski test već pokriva logiku, ovo je vizuelna/GUI potvrda).
- Pregledati log fajl (`logger deklarant_pro.agent.audit`) tokom stvarne sesije
  rada i potvrditi da su routing/audit linije čitljive i korisne za buduću analizu.
