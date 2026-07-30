# CONTEXT.md — hronologija (arhiva)

> Ovo je hronološki, append-only log sesijskih odluka (bivše sekcije 15+ iz
> docs/CONTEXT.md, podijeljeno 2026-07-30 zbog veličine — fajl je narastao na
> ~440k tokena pri punom čitanju, a docs/CONTEXT.md se čita OBAVEZNO u svakoj
> sesiji za svakog agenta).
>
> **NE čitati ovaj fajl u cijelosti.** Pretražiti (Grep/grep) po ključnoj riječi,
> temi ili datumu — svaka sekcija je samostalna i naslovljena temom + datumom.
> MCP `search_project_memory` često već pokriva isti sadržaj bez potrebe za
> otvaranjem ovog fajla. Detaljniji izvor za svaku stavku je u `agent_reports/`
> ili `project_rooms/` — ovaj fajl je kratak sažetak, ne zamjena za njih.
>
> Nove dated stavke se dodaju OVDJE (na kraj), ne u docs/CONTEXT.md — vidi
> pravilo u docs/CONTEXT.md §13.

---

## 15. Multiagentski harness (2026-07-18)

`AGENTS.md` u korijenu je KANONSKI fajl pravila za sve agente (Claude, Codex,
DeepSeek, GLM, Kimi, MiniMax...). `CLAUDE.md` ga importuje (`@AGENTS.md`) i sadrži
samo Claude-specifičnu memoriju — pravila se mijenjaju isključivo u AGENTS.md.
Git pre-commit hook (`scripts/git-hooks/pre-commit`) sprovodi py_compile na staged
.py fajlovima + podsjetnike za Korak 1-5; instalacija po mašini:
`git config core.hooksPath scripts/git-hooks`. Ne zaobilaziti sa `--no-verify`.

---

## 16. Decision servis — TariffMapping nema supplier polje (poznat gap)

`TariffMapping` dataclass (`services/tariff/tariff_mapping_service.py`) NE nosi
`supplier` polje iako kolona postoji u `catalogs.product_tariff_mapping`.
`services/decision/evidence_adapters.py::adapt_tariff_evidence()` je zato
provjeru "isti izvoznik" radila poredeći ime izvoznika sa `naziv_robe` (naziv
PROIZVODA) — praktično uvijek `False`. Popravljeno 2026-07-19: kandidat se sad
prijavljuje kad je `mapping.similarity >= 0.99` (tačan `product_code` match),
bez obzira na `usage_count` — bitno jer odmah nakon ručne ispravke (desni klik
→ `correct_mapping()`) `usage_count` je uvijek 1. Vidi
`agent_reports/2026-07-19_evidence-adapter-exact-match-fix.md`.

**Follow-up koji ostaje otvoren**: prava popravka `is_same_exporter` zahtijeva
dodavanje `supplier` polja u `TariffMapping` + `find_mapping()` SELECT — ali
`services/tariff/tariff_mapping_service.py` se u `dist_client` kompajlira u
Nuitka `.pyd` (`dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd`).
Svaka izmjena tog fajla zahtijeva pun rebuild (`scripts/build_distribution.bat`
ili ciljani `python -m nuitka --module`) da bi se vidjela na Windows klijentu —
ne raditi tu izmjenu bez plana za rebuild i verifikaciju.

### GitNexus indeks degradiran za ovaj repo (2026-07-19)
`gitnexus_impact`/`gitnexus_context` ne prepoznaju ni osnovne, davno postojeće
simbole (npr. `TariffMappingService`) iako je index ranije prijavio "uspješno
ažuriran". `gitnexus_detect_changes` i dalje radi (file-diff nivo), ali vraća
`changed_symbols: []` za stvarno izmijenjene funkcije. Dok se ne istraži,
tretirati GitNexus impact izlaze sa oprezom i raditi ručnu (grep-based) impact
analizu kao dopunu, ne zamjenu.

---

## 17. `catalogs` šema — 6 tabela uklonjeno (2026-07-19), poznata "smeće" mjesta

Audit cijele `catalogs` šeme (36 tabela) pokazao je da je većina (26) aktivno
korišćena — baza NIJE bila haotična kako se činilo, ali je imala jasne ostatke.
Uklonjeno (migracija `database/migrations/009_drop_unused_tables.sql`, backup u
`database/backups/2026-07-19_pre_cleanup/`, lokalno, gitignored):
`product_tariff_mapping_backup`, `tariff_knowledge_base_backup`,
`supplier_profiles`, `supplier_historical_profiles`, `postupci_rb37`,
`declaration_drafts`. Detalji: `agent_reports/2026-07-19_baza-podataka-audit-katalog.md`
i `agent_reports/2026-07-19_baza-cleanup-drop-6-tabela.md`.

**Zamka koju treba znati za buduće DROP TABLE na ovoj bazi**: prije brisanja
BILO KOJE tabele sa `id SERIAL`/`nextval(...)` provjeriti da li sekvenca dijeli
ime-šablon sa nekom drugom (živom) tabelom — `product_tariff_mapping_backup.id`
je koristila `product_tariff_mapping_id_seq` (bez sufiksa), dok živa
`product_tariff_mapping.id` koristi `product_tariff_mapping_id_seq1`. Da su iste,
`DROP TABLE` bi (PostgreSQL automatski briše `OWNED BY` sekvencu) obrisao
sekvencu žive tabele. Provjera: `pg_depend` join na `pg_class`/`pg_attribute`
(vidi agent_report za tačan upit) — NIKAD ne pretpostavljati na osnovu imena.

**Još uvijek nekorišćeno, ali NIJE uklonjeno** (kod ih poziva, samo su
podaci/rezultat upitni — treba ljudska odluka o namjeni prije akcije):
`tarifa_nazivi` (GUI poziva, nikad napunjena), `exporter_xml_index` (cache se
čini da se nikad ne "pogađa" od bulk uvoza 2026-06-13),
`product_similarity_memory` (embedding indeks nad `product_tariff_mapping`,
sync stao ~2 mjeseca — NIJE duplikat, samo neaktivno održavan).

`database/migrate_tariff_kb.py` i `database/ingest_tariff_kb.py` i dalje su dio
`database/setup_all_migrations.py` provizionog pipeline-a i kreiraju praznu,
nekorišćenu `tariff_knowledge_base` tabelu (bez `_backup` sufiksa) na svakoj
novoj instalaciji — namjerno netaknuto, jer je to promjena instalacionog
procesa, ne samo čišćenje postojeće baze.

---

## 18. MCP historijska pretraga — `declarations`/`declaration_items` popunjeni pravim XML podacima (2026-07-19)

**Ispravka pogrešne pretpostavke**: ranije se mislilo (i pogrešno tvrdilo
korisniku) da `migrate_mappings.py` puni ove tabele iz "stvarno prihvaćenih
ASYCUDA deklaracija". Netačno — ta skripta je samo omotavala
`catalogs.product_tariff_mapping` u lažne `"MIGRATED_*"` deklaracije (isti
podaci, druga šema, i uz to `LIMIT 1000`). Nula dodane evidentne vrijednosti.

**Prava istorija ASYCUDA deklaracija već postoji** i koristi je
`services/agent/chat/declaration_search_service.py` — parsira 2503 stvarna
XML fajla iz `data/knowledge_base/NOVA ASIKUDA/` u lokalni SQLite indeks
(`declaration_index.db`) za agent chat pretragu ("slični proizvodi",
tarifni prijedlozi). **MCP server ne može direktno dijeliti taj SQLite
indeks** jer je arhitekturno namijenjen da radi samostalno na Ubuntu serveru
sa SAMO PostgreSQL pristupom (`docs/sections/mcp-server-architecture.md`) —
otuda odvojen PostgreSQL put.

Napravljena nova skripta `database/migrate_declarations_from_xml.py` koja
**reuse-uje** `DeclarationSearchService._parse_xml()` (dokazana logika, ne
nova reimplementacija) i puni `catalogs.declarations`/`declaration_items` sa
2496 stvarnih deklaracija / 9798 stavki. Svih 6 MCP alata
(`mcp_server/tools/*.py`) sad vraćaju stvarne rezultate. Jednokratni backfill
(korisnikova eksplicitna odluka, ne inkrementalni sync) — novi XML fajlovi
dodani nakon 2026-07-19 neće biti vidljivi dok se skripta ručno ne ponovi.

**Poznato ograničenje, nije popravljeno**: `search_historical_declarations` i
srodni alati u `mcp_server/tools/*.py` koriste prostu `ILIKE`, nisu
dijakritik-neosjetljivi (mora se tražiti "čvarci", "cvarci" ne pronalazi
ništa) — za razliku od SQLite verzije koja koristi FTS5
`remove_diacritics` tokenizator. Follow-up: PostgreSQL `unaccent` extension.

Detalji: `agent_reports/2026-07-19_mcp-historijska-pretraga-real-xml.md`.

---

## 19. Preostale 3 tabele riješene (2026-07-19) — tarifa_nazivi, exporter_xml_index, product_similarity_memory

`tarifa_nazivi` obrisana (migracija 010) — mrtav widget `GoodsNameEdit`, nikad
wired u GUI (nije izvezen iz `gui/widgets/__init__.py`).

`exporter_xml_index` — `increment_use_count()` nije imala nijednog pozivaoca,
pa su `use_count`/`last_used` bili zamrznuti od bulk uvoza (2026-06-13) iako je
sama pretraga (`find_xml_for_pair`/`find_xml_by_consignee`) aktivno radila.
Dodana `_mark_hit()` helper — poziva se na svih 7 return-tačaka obje funkcije,
cilja tačan red preko `id` (ne preko exporter_normalized koji može pogoditi
više redova).

`product_similarity_memory` — sync nikad nije bio automatizovan
(`scripts/sync_product_similarity_memory.py` + `embed_product_similarity_memory.py`
samo ručni CLI). `app/run.py` sad pokreće provjeru pri svakom startu (isti
obrazac kao `_start_mcp_server` — pozadinski daemon thread, ne blokira UI):
ako je `MAX(updated_at)` starije od 7 dana, pokreće sync+embed.

**Bitan nalaz**: `sentence-transformers` (paket potreban za "local" embedding
provider — default kad `PRODUCT_SIMILARITY_EMBEDDING_PROVIDER` nije podešen u
`.env`) nije bio ni instaliran ni deklarisan kao zavisnost — embed korak nikad
nije mogao raditi. Dodan kao opcioni extra `embeddings` u `pyproject.toml`
(isti obrazac kao `ocr` extra) + `requirements-embeddings.txt`. Model
(`all-MiniLM-L6-v2`) mora se preuzeti jednom sa interneta (keš u
`~/.cache/huggingface/`) — kod nakon toga radi sa `local_files_only=True`
(potpuno offline). Na svježoj instalaciji bez tog keša, prvi embed poziv će
pući dok se model ručno ne preuzme — namjerno nije automatizovano da prvi
start aplikacije ne pravi mrežni poziv bez znanja korisnika.

Detalji: `agent_reports/2026-07-19_preostale-3-tabele-tarifa-exporter-similarity.md`.

---

## 20. Agent mode Faza A — sigurnosna kapija za upisi_u_kolonu (2026-07-19)

`upisi_u_kolonu` je bio jedini agent alat koji je direktno pisao u draft bez
potvrde korisnika (i Tool Use i regex fallback put) — poruka "upiši zemlja
porijekla RS" je mijenjala SVE stavke Faktura taba prije bilo kakvog pregleda.
Popravljeno korišćenjem **postojeće, ranije nekorišćene** proposal-card
infrastrukture (`ProposalCardWidget`, `show_proposal_card`/
`_on_proposal_confirmed`/`_on_proposal_rejected` u `chat_intent_handler.py`) —
ti pozivi su postojali u kodu bez ijednog stvarnog pozivaoca prije ove izmjene.

Uveden `services/agent/chat/tool_policy.py` — `ToolEffect` (READ_ONLY/PROPOSE/
MUTATE) registry za svih 12 agent alata, fail-closed za nepoznat alat.

**Ključna integracija**: potvrđen upis u tarifni_broj/zemlja_porijekla/
povlastica sad zove `sync_decision_state_after_manual_edit()` (Decision
Service, Faza 0-6 od 2026-07-18) po liniji — bez ovoga bi `upisi_u_kolonu`
postao treći paralelan upisni put mimo `DeclarationDecisionService`.

**Poznat gap, nije riješen**: nema `operation_id` — dvije uzastopne
eksplicitne invokacije `_on_proposal_confirmed` bi izvršile mutaciju dvaput.
GUI je djelimično zaštićen (widget se uništava nakon klika), replay signala
nije. Dokumentovano kao `xfail` test, ne lažno predstavljeno kao riješeno.

**Netraćen test fajl otkriven**: `tests/test_tool_use_offline.py` (solidan
test suite za Tool Use, 30+ testova) NIKAD nije bio u git istoriji —
`.gitignore:78` isključuje `test_*.py` direktno pod `tests/` (scratch
konvencija), izuzev `tests/*/test_*.py`. Izmjene tamo su lokalne samo na ovoj
mašini. Tracked pokrivenost za ovu fazu: `tests/unit/test_tool_policy.py`,
`tests/unit/test_agent_mutation_gate.py`.

Faze B-F plana (`docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md`)
nisu rađene — korisnik je eksplicitno tražio samo Fazu A, pa stop za pregled.

Detalji: `agent_reports/2026-07-19_faza-a-sigurnosna-kapija-mutirajuci-alati.md`.

---

## 21. Agent mode Faza B — LLM provider unifikacija, DeepSeek/OpenRouter uklonjeni (2026-07-19)

`services/agent/chat/tool_dispatcher.py` je pozivao DeepSeek direktno (mimo
`LLMProvider`) — kršenje AGENTS.md "LLMProvider ostaje jedina dozvoljena
ulazna tačka". Zamijenjeno sa `LLMProvider.complete_with_tools()` (nova
metoda, `ProviderToolResponse` neutralan rezultat, Groq → Gemini).

**Poslovna odluka (korisnik eksplicitno potvrdio)**: `LLMProvider` je i dalje
imao OpenRouter i DeepSeek kao 3./4. fallback (neaktivni na ovoj mašini, bez
API ključeva u `.env`, ali prisutni u kodu) — suprotno AGENTS.md politici
("Primarni: Groq; fallback: Gemini... DeepSeek isključen"). **Uklonjeni u
potpunosti** iz `LLMProvider`-a — ako ikad ustreba plaćeni/dodatni fallback,
to je nova, eksplicitna odluka, ne tiha reaktivacija dodavanjem API ključa.

**Otkriven skriven pozivalac**: `gitnexus_impact` na `has_deepseek()` je
otkrio da `gui/tabs/admin/panels/system_panel.py::_on_ai_health_clicked`
(admin AI health check dijagnostika) direktno poziva
`has_deepseek()`/`has_openrouter()`/`deepseek_key`/`openrouter_key` — van
onoga što je plan predvidio. Bez ove popravke, klik na "AI Health Check" bi
pucao (`AttributeError`). Dobar podsjetnik da `gitnexus_impact` treba
pokrenuti i za "očigledne" izmjene — plan ne vidi sve vanjske pozivaoce.

Detalji: `agent_reports/2026-07-19_faza-b-llm-provider-unifikacija.md`.

---

## 22. Agent mode Faza C — pouzdan status pune automatizacije (2026-07-19)

`gui/tabs/agent/services/import_pipeline_service.py::_puna_auto_pipeline`
nije imao konzistentan mehanizam da zaustavi pipeline nakon kritičnog pada
jedne faze — nastavljao bi na sljedeću fazu (auto-popuna → validacija →
naimenovanja) čak i kad je prethodna faza (npr. izračun masa) pukla, jer
4 View metode u `faktura_view.py` (`_on_calculate_masses`, `_on_auto_fill`,
`_on_validate_all`, `_on_create_naimenovanja`) nisu imale konzistentan
povratni ugovor iz kojeg bi se ishod mogao pouzdano pročitati. Popravljeno:
sve 4 metode sad vraćaju strukturisan rezultat (bool/tuple); novi
`PipelineStageResult` model (`gui/tabs/agent/services/pipeline_stage_result.py`)
prati ishod svake faze; kritična faza odmah zaustavlja pipeline umjesto da
"tiho" propadne kroz preostale korake.

**Otkriven skriven bug (auto mod je i dalje prikazivao blokirajući dijalog)**:
`_run_historical_tariff_validation(modal=auto)` je u punoj automatizaciji
(`auto=True`), kad postoje istorijski prijedlozi tarifa, otvarao
BLOKIRAJUĆI Qt modalni `TariffValidationDialog` i čekao korisnika — potpuno
suprotno namjeri "auto mod = bez dijaloga", praktično bi zamrznuo pipeline
bez ijedne poruke u chatu. Fix: zaseban `auto` parametar koji dijalog
potpuno preskače (samo loguje broj prijedloga) umjesto da ga čini modalnim.
Isti obrazac (dijeljeni `ErrorHandler.handle_*_error()` bez `auto`-guard-a)
popravljen na 3 mjesta u `faktura_view.py` — inače bi i tu blokirajući
dijalog iskrsnuo usred bezglave automatizacije.

**Namjerno NIJE povezano sa `WorkflowState`** (`gui/tabs/agent/workflow_state.py`):
`WorkflowState.APPLYING` nije dostižan iz `WorkflowState.COMPLETED`, stanja
koje `agent_controller.py` postavlja neposredno prije poziva
`_puna_auto_pipeline` — dodavanje tranzicija bi zahtijevalo restrukturiranje
state machine-a, van scope-a ove faze. `PipelineStageResult` ostaje uži,
zaseban koncept po nivou pojedinačne faze, ne cijele sesije.

Detalji: `agent_reports/2026-07-19_faza-c-pouzdan-status-pune-automatizacije.md`.

---

## 23. Agent mode Faza D — standardizovani rezultati i audit (2026-07-20)

`ToolResult` je do sada imao strukturisan oblik samo za needs_review/unknown/error
— uspješan rezultat nije. Dodana polja `effect`/`confirmation_required`/
`operation_id` + `ToolResult.ok()`. Novi `services/agent/chat/audit_log.py`
(logging-baziran, NE nova DB tabela — vidi obrazloženje u agent reportu) bilježi
strukturisan zapis za sve routing slojeve: contextual/local/tool_use/regex_fallback/
plain_chat/pipeline.

**Zatvoren poznat gap iz Faze A** (plan §16, dokumentovan kao `xfail(strict=True)`
test): `_propose_kolona_upis` sad dodjeljuje `operation_id` koji
`_on_proposal_confirmed`/`_on_proposal_rejected` atomarno konzumiraju PRIJE
izvršenja — drugi/repliciran signal na istoj proposal kartici je no-op umjesto
dvostrukog upisa u draft.

**Otkriveno i ispravljeno usput (dead code)**: `chat_intent_handler.py::_on_error`
je provjeravao poruku greške `"deepseek api ključ nije podešen"` — ta grana je
bila mrtav kod od Faze B (DeepSeek trajno uklonjen iz `LLMProvider`, ta poruka se
više nikad ne može desiti). Zamijenjena tačnom provjerom stvarne poruke
(`"nema dostupnog ai providera"`). Isti obrazac (stale DeepSeek referenca) nađen
i u `tool_dispatcher.py` docstring-u.

**GitNexus CRITICAL nakon ove faze — provjereno i objašnjeno, nije stvaran rizik**:
141 promijenjenih simbola/36 affected_processes je artefakt obima (9 fajlova u
jednom prolazu) i GitNexus fan-out brojanja kroz centralne funkcije
(`ChatWorker.run`, `_pg_today_stats`) — 5 od 9 fajlova su isključivo `print()`→
`logger` konverzije unutar `except` blokova (provjereno liniju-po-liniju, nulti
uticaj na kontrolni tok/return vrijednosti). Jedina promjena oblika postojećeg
ugovora (Qt signal `tool_call_received`/`fallback_to_chat` dobio `provider`
parametar) ima tačno jednog pozivaoca u cijelom repou, već ažuriranog. Puna
analiza: `project_rooms/2026-07-20_faza-d-standardizovani-rezultati-audit.md`.

Detalji: `agent_reports/2026-07-20_faza-d-standardizovani-rezultati-observability.md`.

---

## 24. Autosave / recovery nacrta deklaracije (2026-07-20)

**Dodat servis `services/draft_autosave_service.py`**: periodično automatsko
čuvanje trenutnog nacrta (svakih 5 min) + odmah nakon kreiranja naimenovanja
(hook na `FakturaView.naimenovanja_created` signal). Čuva se na fiksnu putanju:
`~/Documents/Deklarant Pro/Nacrti/.autosave/autosave.xml`.

**Ne mijenja postojeće ponašanje**:
- Ne dira `_persistent_draft_path` (ostaje samo za ručno "Sačuvaj nacrt")
- Ne dira `drafts/lastDirectory` QSettings
- Ne prikazuje dijaloge tokom rada — autosave je potpuno tih

**Recovery na startu**: `_check_autosave_on_startup()` u `run.py` — isti
obrazac kao `_check_license_on_startup` (non-blocking, nakon `window.show()`).
Ako autosave fajl postoji, korisnik dobija Yes/No dijalog sa vremenom
zadnjeg autosave-a. Yes → učitava u MainWindow.draft, No → briše autosave.

**Autosave se briše pri urednom zatvaranju** — `clear_autosave()` se poziva
iz `MainWindow.closeEvent()`, NE iz `_on_exit_clicked` (Pi-jev prvi prolaz je
imao poziv samo tamo — code review nalaz: `closeEvent` se okida i pri
zatvaranju preko standardnog Windows X dugmeta u naslovnoj traci, ne samo
preko custom "Izlaz" dugmeta u tab traci; bez pomjeranja u `closeEvent`,
svaki izlazak preko X dugmeta je ostavljao lažni "nesačuvan rad" prompt na
sljedećem startu iako nije bilo pada). `_on_exit_clicked` više ne zove
`clear_autosave()` direktno — `self.close()` na kraju te metode ionako
okida `closeEvent`, koji sad pokriva oba puta zatvaranja.

**Grana**: `feature/draft-autosave-nacrt`, spojena u `windows` nakon Faze D.
Detalji: `agent_reports/2026-07-20_pi-autosave-nacrt.md` (Pi),
`agent_reports/2026-07-20_review-fix-autosave-closeevent.md` (Claude review + fix).

**Merge napomena**: nezavisno od ovog autosave rada, `windows` je (fix commit
`879a93e`, nakon Faze D) dodao `_confirm_safe_to_exit()` provjeru u isti
`closeEvent()` — ista motivacija ("X dugme zaobilazi provjere"), drugi problem
(upozorenje da agent još radi u pozadini, ne autosave brisanje). Automatski
(git ort) merge je ispravno spojio oba — `closeEvent()` sad redom: provjerava
agent worker → čuva geometriju prozora → briše autosave → `super().closeEvent()`.

---

## 25. Dist runtime i tarifna safety mreža (2026-07-21)

`dist_client` učitava `tariff_facade`/`tariff_mapping_service` iz `.pyd`, ali
`hybrid_tariff_agent` iz običnog `.py`; dist i source hash tog fajla su isti i oba
sadrže aktivni `_decide_free()` put. XML builder je takođe `.py`; trenutni dist diff
mijenja samo dokumentaciju/logovanje, ne XML logiku. Prije tarifnog fixa obavezni su
hash instaliranog klijentskog artefakta i izolovana PostgreSQL test baza sa rollbackom.
Agent `AuditEvent.extra` se trenutno ne ispisuje u log, a GUI auto-fill nema audit trag.

---

## 26. PyInstaller rebuild + audit_log.extra fix (2026-07-21)

**Dvije distribucije, ne dvije alternative.** `dist_client/` (source-mirror +
lokalni `.venv`) i `dist/DeklarantPro.exe` (PyInstaller frozen build) nisu
konkurentske opcije — `dist_client` je razvojna zgodnost (venv ~1GB, cio
source čitljiv), `.exe` je jedini realan isporučni artefakat klijentu.
Zatečeni `.exe` je bio od 9. juna (250 commitova zaostatka). Rebuildovan iz
trenutnog `windows` HEAD-a preko root `deklarant_pro.spec` (builda iz
`run.py`, `pathex=[ROOT]` — čist source, ne dist_client). `dist_client/
deklarant_pro.spec` (drugi, stariji spec fajl koji je pravio pometnju
"koji je pravi") obrisan — root spec je jedini kanonski. Smoke test:
`.exe` pokrenut, GUI se ispravno renderuje (uklj. učitanu sesiju sa EUR.1
dijalogom), 78MB exe / 1.5GB cio folder (torch bundle zbog embeddings
extra-a). **Rebuild treba ponoviti nakon svake veće izmjene** — nema
automatskog CI koraka za ovo.

**`AuditEvent.extra` fix** (Codex-ov nalaz, §6.11 tehničke analize,
potvrđen čitanjem koda): `audit_log.py::record()` je primao `extra` dict
(npr. `operation_id` iz `_on_proposal_confirmed`) ali ga nikad nije
uključivao u `logger.info()` format string — polje je postojalo u memoriji
(idempotencija je radila ispravno), ali se gubilo prije nego uđe u stvarni
audit zapis. Popravljeno dodavanjem `extra=%s` u format string. GitNexus
impact na `record()`: HIGH (34 pozivaoca/fan-in), ali izmjena čisto
aditivna — 0 affected_processes nakon fix-a.

Detalji: `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md`
§6.0/§6.11, `agent_reports/2026-07-21_opus-review-dopuna-tehnicke-analize.md`.

---

## 27. Preciznost tarifnih prijedloga — Auto-popuni + Provjeri (2026-07-21)

**Auto-popuni (Faktura toolbar) — otkriven P0 bug**: dijalog za potvrdu (`suggest_fast()`,
bez dobavljača, prag 0.70) i stvaran upis (`auto_populate_tariffs()`, sa dobavljačem +
istorijom XML deklaracija) su bila DVA NEZAVISNA proračuna — tarifa koju korisnik odobri
nije nužno bila tarifa koja se upiše. Popravljeno: `TariffMappingService.auto_populate_tariffs(
dry_run=True)` računa `TariffProposal` listu bez upisa; `commit_proposals()` upisuje TAČNO
te prijedloge bez ponovnog računanja. `min_similarity` default 0.70 → 0.92 (projektni kanon).

**Istorijska validacija ("Provjeri") — dvije zbunjujuće brojke**: "Podudarnost %"
(`match.confidence`) mjeri UČESTALOST KORIŠTENJA (`0.60 + usage*0.003 + 0.05`), ne
tekstualnu sličnost naziva — preimenovano u "Učestalost korištenja". "Sigurnost preporuke"
je uvijek pokazivala FIKSNU konstantu (60/75/90/100 po `DecisionConfidence` kategoriji) —
stvarni `TariffDecision.score` se računao ali nikad nije stizao do UI-ja. **Probano i
odbačeno**: prosljeđivanje `decision.score` u `build_evidence()` — score<50 (čest za
show_weak) bi prebacio prijedlog u HIDDEN (crvenu) kategoriju iako je aktivno prikazan.
Sigurnije rješenje: dijalog prikazuje `match.decision_score` (već izračunat, samo
neprikazan) kao broj, `evidence.score`/boja bedža ostaju netaknuti — `build_evidence()`
(CRITICAL, 44 pozivaoca) nije dirano.

**Otkriveno tokom dist_client mirroringa — `.pyd` sloj širi nego pretpostavljeno**:
`tariff_mapping_service.py`/`tariff_facade.py` u dist_client su SAMO kompajlirani `.pyd`
(nema `.py` para) — mirror fizički nemoguć bez Nuitka rekompilacije. Isto važi za
`core/licensing`, `core/validation`, `services/declaration_assembly`, `services/export_service`,
`services/faktura`, `services/licensing`, `services/tariff_controls_service`,
`services/tariff_doc_history_service`, `services/tariff_tree_service`, `services/validation`.
**Ne utiče na `.exe`** (builda iz root `.py` source-a preko `deklarant_pro.spec`), utiče
SAMO na interaktivni `dist_client` venv put (`start_debug.bat`).

Detalji: `agent_reports/2026-07-21_preciznost-tarifnih-prijedloga.md`,
`project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md`.

**Dopuna (isti dan) — korisnička primjedba nakon testiranja na rebuildovanom `.exe`-u**:
"Sigurnost preporuke" broj i tekstualna labela (jak/srednji/slab) i dalje su djelovali
kontradiktorno (npr. "slab (72%)") jer `match.decision_score` (kontinuiran, iz
`decide_tariff_match`) i `tariff_confidence_label` (diskretna `DecisionConfidence`
kategorija) dolaze iz dva nekalibrisana sistema. Dodata `score_band_for_confidence()`
(čisto aditivna, `core/decision/evidence.py`, ne dira `build_evidence`) — vraća (min, max)
opseg po kategoriji, isti pragovi kao `evidence_score_category()` (95/85/70/50). Dijalog
sad ulašti sirov `decision_score` u taj opseg prije prikaza — broj i dalje varira, ali
nikad ne izgleda jače/slabije od riječi pored njega.

**Dopuna 2 (isti dan) — "korišten Nx" ≠ "verifikovano tačno"**: korisnik primijetio da
istorijska validacija tretira "carina nije odbila N puta" kao jak dokaz, iako carina radi
SELEKTIVNU kontrolu (ne pregledava svaku stavku) — isti obrazac kao poznat bug GREJAC
SPIRALA/Plamenik (jedna greška se ponavlja i izgleda pouzdano samo zato što se ponavlja).
Otkriveno: sistem VEĆ ima jači signal — `catalogs.user_feedback` pamti kad je ČOVJEK
eksplicitno potvrdio baš taj par kroz "Provjeri" dijalog — ali se to koristilo SAMO da
tiho auto-primijeni promjenu (`HistoricalTariffSearchService._feedback_action` →
"accept" grana), bez ikad obavijestiti korisnika šta se promijenilo i zašto. Popravljeno:
`FakturaView._notify_auto_applied_tariffs()` (novo) prikazuje jasnu poruku u interaktivnom
modu — nabraja auto-primijenjene stavke i eksplicitno navodi da je razlog ranija ručna
potvrda, uz poziv da se ponovo provjeri. U auto modu (puna automatizacija) samo se loguje.

**Dopuna 3 (isti dan) — "Provjeri" ignorisao selekciju redova**: korisnik prijavio da nakon
selektovanja N stavki u Faktura tabeli i klika na "Provjeri" (dugme pored Bruto/Neto,
`btn_validate` → `_on_validate_all` → `_run_historical_tariff_validation`), tarifni brojevi
"koji su došli iz fakture" ostaju nepromijenjeni čak i nakon prihvatanja prijedloga. Uzrok:
funkcija je UVIJEK provjeravala SVE `draft.invoice_lines`, bez obzira na selekciju u tabeli —
za razliku od Auto-popuni (`_on_auto_fill`), koji već poštuje `table.selectionModel()`.
Kad korisnik selektuje 1-2 konkretne stavke, dijalog je prikazivao prijedloge za desetine
NEPOVEZANIH redova — lako je moguće prihvatiti prijedlog za pogrešan red misleći da je to
baš selektovana stavka. Popravljeno: `_run_historical_tariff_validation` sada gradi
`target_lines` iz `selected_row_indexes` (isti obrazac kao Auto-popuni) kad selekcija
postoji i `auto=False`. **Kritičan detalj**: `HistoricalTariffSearchService.validate_lines`
vraća `match.line_index`/`last_auto_applied` kao poziciju UNUTAR proslijeđene liste (0..N-1),
ne stvarni red u `draft.invoice_lines` — bez remapiranja nazad (`row_indexes[local_idx]`)
promjena bi se upisala u POGREŠAN red tabele kad je selekcija filtrirana lista. Testovi:
`tests/unit/test_faktura_view_provjeri_selekcija.py` (4 nova, uklj. regresioni test za
remapiranje indeksa).

**Dopuna 4 (isti dan) — 3 nalaza nakon testiranja rebuildovanog `.exe`-a**:
1) Selekcijski fix je otkrio da "nema prijedloga" grana (`if not matches: return`) NIKAD
   nije davala korisniku ikakvu potvrdu — prije scoping-a to je bilo rijetko primjetno (94
   stavki skoro uvijek nešto vrati), ali kad je "Provjeri" scoped na 1-2 selektovane stavke,
   tišina se lako protumači kao da dijalog "nije htio da se otvori". Dodato: eksplicitna
   `QMessageBox.information` SAMO kad je `row_indexes is not None` (aktivna selekcija) i nema
   `auto_applied` — bez selekcije tišina ostaje namjerna (ne zamarati na svaki klik za
   desetine stavki).
2) `lbl_total_quantity` ("Komada") je prikazivao `total_quantity:,` bez `int()` — `kolicina`
   je float, pa zbir (npr. 8045.0) prikazuje "8,045.0". U carinskom postupku količina MORA
   biti cio broj (ne postoji decimalna količina komada) — fix: `int(round(total_quantity))`.
3) `_build_analysis_summary_from_draft` (status bar "🌍 Porijeklo") je u komitu `735400a`
   ("style(faktura): sažmi statusnu traku", Co-Authored-By: OpenAI Codex, 2026-07-21 16:44)
   IZGUBIO breakdown po zemlji (`DE:9 | IT:8...`) — zamijenjen golim brojem ("9 zemalja").
   Korisnik je eksplicitno tražio da se breakdown vrati (bitno je koliko naimenovanja
   pripada kojoj zemlji, ne samo broj zemalja). `dist_client` kopija NIJE imala ovu
   regresiju (zaostala/nesinhronizovana sa tim komitom) — root vraćen da odgovara
   dist_client-u. **Napomena za buduće agente**: ako opet neko "sažme" ovu statusnu traku,
   provjeriti sa korisnikom prije brisanja breakdown-a — već je jednom vraćen na
   eksplicitan zahtjev. Testovi: `tests/unit/test_faktura_view_status_bar.py` (3 nova).

**Dopuna 5 (isti dan) — "Provjeri" ne vidi XML arhivu direktno (SUSSINA slučaj, NEDOVRŠENO)**:
korisnik prijavio da za SUSSINA 650/200 tbl. (trenutni tarifni broj 38249993, poglavlje 3824)
"Provjeri" kaže "nema boljeg prijedloga", iako `data/knowledge_base/NOVA ASIKUDA/` sadrži
33 XML fajla gdje je SUSSINA UVIJEK 21069098 (poglavlje 2106 — prehrambeni proizvod/dodatak,
100% konzistentno). **Uzrok NIJE bug u matching logici** — `HistoricalTariffSearchService`
traži isključivo u `catalogs.product_tariff_mapping` (PostgreSQL), koja se puni SAMO ručno
kroz Admin → "Učenje iz XML-ova" (`_ReindexWorker` → `TariffMappingService.
import_from_xml_files()`, `gui/tabs/admin/panels/learning_panel.py`) — nema automatskog
triggera. Ako reindex nije pokretan otkad su ovi XML fajlovi dodati u arhivu, baza "ne zna"
za njih, pa je "nema boljeg prijedloga" tehnički tačno za bazu ali pogrešno u praksi (arhiva
ima dokaz, baza ga nije apsorbovala). **Provjera blokirana**: agent okruženje trenutno nema
mrežni pristup PostgreSQL serveru (192.168.100.154 timeout sa `192.168.0.27` — ista mrežna
podjela kao na početku ove sesije), pa nije potvrđeno direktnim upitom da li je red za
SUSSINA/21069098 uopšte u `product_tariff_mapping`. **Sljedeći korak (kad se nastavi)**:
korisnik treba pokrenuti Admin → "Učenje iz XML-ova", zatim ponovo "Provjeri" na istoj
fakturi; ako i dalje ništa ne predloži, provjeriti `MIN_USAGE_FOR_CROSS_CHAPTER = 5` prag u
`historical_tariff_search_service.py` (2106→3824 je cross-chapter skok koji zahtijeva
usage_count ≥ 5 da ne bude suprimiran) i/ili da li `_is_noisy_name`/`_clean_product_name`
(u `tariff_mapping_service.py::import_from_xml_files`) ispravno zadržava "SUSSINA" iz
`Commercial_Description` teksta (koji je mješavina generičkog boilerplate-a i imena
proizvoda, npr. "prehrambeni proizvodi... ostali:; ostali. SUSSINA").

## 28. Desktop prečica pokreće `dist_client/`, ne PyInstaller `.exe` — DVIJE odvojene `.env` kopije (2026-07-22)

Korisnik promijenio `DB_HOST` u (root) `.env` sa stare IP na `192.168.0.25`, ali aplikacija
i dalje nije mogla da se konektuje. Uzrok: Desktop prečica `Deklarant Pro.lnk` NE pokreće
`dist/DeklarantPro/DeklarantPro.exe` (PyInstaller build) — pokreće
`dist_client/start_silent.vbs` (venv-based runtime, `WorkingDirectory: dist_client/`).
`config/settings.py` učitava `.env` iz `PROJECT_ROOT` koji se računa relativno na trenutni
proces (`Path(sys.executable).parent` kad je frozen, inače `Path(__file__).parent.parent`) —
za `dist_client/` runtime to je `dist_client/.env`, POTPUNO ODVOJEN fajl od root `.env`.
`dist_client/.env` je i dalje imao `DB_HOST=192.168.100.25` (druga podmreža) — korisnikova
izmjena u root `.env` nije imala nikakav efekat na ono što stvarno pokreće.

**Provjereno direktnim `psycopg2.connect()` pozivom (ne samo TCP test)**: `192.168.0.25:5432`
je potpuno dostupan i kredencijali rade — mrežni/DB sloj nije bio problem, samo pogrešan
`.env` fajl. Popravljeno: `dist_client/.env` DB_HOST → `192.168.0.25` (nije commitovano —
oba `.env` fajla su u `.gitignore`, ovo je samo runtime konfiguracija na ovoj mašini).

**Napomena za buduće agente**: kad korisnik prijavi "promijenio sam .env ali ne radi",
PRVO provjeriti koju prečicu/launcher korisnik stvarno koristi (Desktop `.lnk` →
`dist_client/start_silent.vbs` na ovoj mašini) prije nego se pretpostavi da je root `.env`
relevantan. Ne postoji trenutno automatska sinhronizacija između root `.env` i
`dist_client/.env` — obje kopije treba ručno ažurirati pri promjeni server IP-a.

## 29. SUSSINA riješeno — pravi bug je hard supplier filter, ne zastarjela baza (2026-07-22)

Nastavak §27 dopune 5. Kad je baza postala dostupna, direktan upit je pokazao da mapping
`SUSSINA 650 tbl. → 21069098` (usage_count=40) postoji od **aprila 2026** — reindeksiranje
(310 novih parova) NIJE bio uzrok niti rješenje. Pravi bug: `HistoricalTariffSearchService.
_search_one()` je, kad je izvoznik poznat, primjenjivao TVRD filter `AND supplier ILIKE
'%kljuc%'` — a baš najčistiji, najkorišteniji zapisi za SUSSINA (usage 24-40) su učeni BEZ
upisanog dobavljača (`supplier=''`), dok su zapisi SA dobavljačem generički/messy tekst iz
`Commercial_Description` sa niskim usage_count (3-4). Filter je tiho isključivao najjači
dokaz u korist slabijeg, koji onda nije prošao `decide_tariff_match` prag → "nema boljeg
prijedloga" iako je arhiva imala jasan, dosljedan odgovor.

**Fix**: `_execute()` WHERE klauzula sad prihvata `supplier ILIKE %s OR supplier IS NULL OR
supplier = ''` — nepoznat dobavljač više NE isključuje zapis (zaštita od miješanja tarifa
DRUGOG, potvrđenog dobavljača ostaje netaknuta). `_to_matches()` prije je primala JEDAN
`supplier_matched: bool` za CIJEL upit — sad se `supplier_match` računa PO REDU
(`supplier_key.lower() in supplier.lower()`), jer rezultat sad može biti mješavina
potvrđenih i nepotvrđenih zapisa. Testovi: `tests/unit/test_historical_tariff_validation.py`
(3 nova: SQL WHERE sadržaj, per-red supplier_match, end-to-end SUSSINA scenario).

**Napomena za buduće agente**: ovaj obrazac (najbolji istorijski zapis nema upisan
dobavljača) je vjerovatno čest — provjeriti prije zaključka "nema podataka" da li je uzrok
ovaj filter, ne odsustvo podataka. Sporedni nalaz: baza ima i pogrešan par (SUSSINA →
38249993, usage=2) — vjerovatno iz istih pogrešnih deklaracija koje je korisnik prijavio;
nije čišćeno (nema negativan efekat dok jači 21069098 zapis pobjeđuje po usage_count-u).

## 30. "Provjeri" se sad pokreće automatski odmah nakon uvoza fakture (2026-07-22)

Direktan nastavak §29 — korisnik pitao kako trajno riješiti da se pogrešno tarifirana roba
(SUSSINA tip greške) uhvati čim se uveze, umjesto da zavisi od toga da neko naknadno klikne
"Provjeri". Razmotrene dvije opcije: (a) tiha notifikacija u statusnoj traci, (b) automatsko
pokretanje POSTOJEĆEG punog modala (`TariffValidationDialog`) odmah nakon uvoza. Korisnik je
eksplicitno izabrao (b) — ništa novo graditi, samo ranije pozvati postojeći kod.

**Implementirano**: `_on_import_finished` (pojedinačni/kombinovani uvoz) i
`_process_batch_records` (grupni uvoz) sad, u svom završnom dijelu, pozivaju
`self._run_historical_tariff_validation(auto=False)` — identičan kod koji se izvršava na
klik dugmeta "Provjeri". Dijalog se pojavljuje SAMO kad ima prijedloga (postojeće `if not
matches: return` ostaje netaknuto) — čista faktura ne prikazuje ništa. Presedan za dijalog
odmah nakon uvoza već postoji u ovom kodu (EUR.1/PE2 potvrde), pa ovo nije novi UX obrazac.

**Agent mod izuzetak — DODANO PA ISTOG DANA UKLONJENO (pogrešna pretpostavka)**: prvobitno
je poziv PRESKAKAN kad je `self._agent_mode` aktivan, pod pretpostavkom da puna
automatizacija (`import_pipeline_service._puna_auto_pipeline`) uvijek sama zove
`_on_validate_all(auto=True)` kasnije. Korisnik je odmah testirao uvoz kroz agent mod i
dobio POTPUNU TIŠINU (ni dijalog ni bilo šta) — ispostavilo se da `self._agent_mode` pokriva
SVE tri agent rute uvoza (`ImportPipelineService`: "Analiza", "Uvezi u deklaraciju", "Puna
automatizacija"), a SAMO "Puna automatizacija" ima taj naknadni poziv. Za druge dvije rute
(uklj. rutu koju je korisnik stvarno koristio) provjera se NIKAD ne bi izvršila.

**Fix**: uslov `if not self._agent_mode:` uklonjen — poziv se sad izvršava UVIJEK, bez
obzira na agent_mode. Sigurno je jer `_puna_auto_pipeline` radi na VEĆ uvezenom draft-u (ne
uvozi sam, pokreće se odvojeno i kasnije preko posebne chat komande "uradi sve") — njen
kasniji `auto=True` poziv ostaje tih (samo log) bez obzira da li je ovaj eager poziv već
nešto prikazao, pa nema stvarnog preklapanja/duplikata.

**Napomena za buduće agente**: `self._agent_mode` ≠ "puna automatizacija je u toku" — to je
opšti "radimo iz agent taba" flag. Ne koristiti ga kao proxy za "pipeline će ovo kasnije
sam odraditi" bez provjere KOJA agent ruta je stvarno aktivna.

Testovi: `tests/unit/test_faktura_view_provjeri_nakon_uvoza.py` (4 — pojedinačni i grupni
uvoz, oba sa/bez agent moda, svi sad očekuju poziv u SVIM slučajevima).

## 31. Agent uvoz je i dalje bio potpuno tih — treći, potpuno drugi kod-put (2026-07-22)

Korisnik testirao rebuild (§30 fix) uvozom kroz agent mod — i dalje NIŠTA automatski, tek
ručni klik "Provjeri" (koji je ispravno predložio 21069098, potvrđujući §29 fix). Uzrok:
agent uvoz NE ide kroz `FakturaView._on_import_finished`/`_process_batch_records` (Qt signal
handleri vezani za obični GUI `ImportWorker`) — ide kroz potpuno ODVOJEN kod-put,
`AgentController._on_all_completed` (`gui/tabs/agent/agent_controller.py`), koji direktno
puni `self.draft.invoice_lines` i zove `fw._load_data_from_draft()` bez ikad prolaska kroz
prethodno popravljene funkcije. §30-ov fix (uklanjanje `_agent_mode` uslova) je bio nužan ali
NEDOVOLJAN — popravio je pogrešan uslov u POGREŠNOM kod-putu.

`_on_all_completed` ima finalnu granu po `self._current_mode`: `"Puna automatizacija"` grana
već zove `self._puna_auto_pipeline(...)` (koji kasnije, u svom koraku 3, zove
`_on_validate_all(auto=True)` — tih/log-only). `else` grana (sve OSTALE agent rute, uklj.
"Uvezi u deklaraciju" — rutu koju je korisnik stvarno koristio) NIJE imala NIŠTA — ni
poziv provjere ni bilo kakvu alternativu.

**Fix**: dodat `if fw and hasattr(fw, '_run_historical_tariff_validation'):
fw._run_historical_tariff_validation(auto=False)` u `else` granu, odmah nakon
`workflow.transition(WorkflowState.COMPLETED)`. Sigurno je jer je ovo JEDINO mjesto gdje
"Uvezi u deklaraciju" (i "Analiza→Uvezi" akcija) završava obradu — nema rizika od duplikata
sa "Puna automatizacija" granom jer su međusobno isključive (`if/else`).

**Napomena za buduće agente — VAŽNO**: ova aplikacija ima NAJMANJE TRI odvojena "uvoz
fakture završen" kod-puta koja SVA moraju biti provjerena kad se dodaje logika "odmah nakon
uvoza": (1) `FakturaView._on_import_finished` (obični GUI import, pojedinačni/kombinovani),
(2) `FakturaView._process_batch_records` (obični GUI grupni uvoz), (3)
`AgentController._on_all_completed` (SVI agent chat uvozi, uklj. "Uvezi u deklaraciju" i
"Puna automatizacija" grane unutra). Provjeriti sva tri prije zaključka da je "auto nakon
uvoza" fix kompletan. Testovi: `tests/unit/test_agent_controller_provjeri_nakon_uvoza.py`
(2 nova — "Uvezi u deklaraciju" dobija poziv, "Puna automatizacija" ne duplira).

## 32. PDF pregled po fakturama — stvarna polja šifre deklaracije (2026-07-21, Codex)

`PDFFakturaPregled.export()` je čitao nepostojeći `draft.sifra_deklaracije`, pa je svaki
izvoz pregleda po fakturama završavao generičkom greškom prije gradnje PDF-a. Šifra u
naslovu sada se sastavlja iz kanonskih polja `deklaracija_tip`, `deklaracija_oznaka` i
`deklaracija_a`. Regresioni test mora napraviti stvarni `%PDF` fajl, ne samo mockovati
ReportLab poziv.

## 33. PDF spisak naimenovanja — ne odbacivati stavke bez veze (2026-07-21, Codex)

`PDFInvoiceExporter._group_by_naimenovanje()` je ranije tiho odbacivao svaku faktura
stavku čiji je `assigned_naimenovanje_ordinal` bio 0. Ako su `draft.items` postojali,
GUI je prijavljivao uspješan izvoz, ali je PDF sadržao samo naslov i datum. Exporter sada
uvijek uključuje takve redove u grupu `STAVKE BEZ NAIMENOVANJA`; ne pokušava sam ponovo
grupisati stavke niti mijenja draft. Regresioni test mora provjeriti tekst stvarno
generisanog PDF-a, a ne samo `%PDF` zaglavlje.

## 34. PDF dijakritici na Windowsu (2026-07-22, Codex)

Oba Faktura PDF exportera prvo traže Liberation Sans, ali taj font standardno nije
prisutan u `C:/Windows/Fonts`; prethodni fallback na ReportLab Helvetica kvario je
`š, ž, č, ć, đ`. Na Windowsu se sada, nakon Liberation Sans pokušaja, registruju četiri
Arial TTF varijante iz sistemskog font direktorija. Test mora iz stvarno generisanog
PDF-a izvući i uporediti tekst `ŠEĆER, ČAJ, ŽITO I ĐEVREK`.

## 35. Faktura toolbar/statusni bar/Naimenovanja stilski redizajn (2026-07-22, Codex)

Codex grana `codex/faktura-toolbar-razmaci` (spojena u `windows` ovog dana) sadrži niz
kozmetičkih QSS/layout izmjena, svaka eksplicitno dokumentovana kao "nisu mijenjani
signali/validacija/poslovna logika": Faktura statusni bar (razdvajanje lijeve/desne zone),
Bruto/Neto/Provjeri blok (spacing/visina), čitljivost glavne tabele, i višestruke iteracije
poravnanja dugmadi "Sačuvaj nacrt"/"Poništi" u naslovnoj traci Naimenovanja (14 uzastopnih
commit-a, probaj-pa-vrati stil). Pojedinačni izvještaji: `agent_reports/
2026-07-22_faktura-statusni-bar-redizajn.md`, `2026-07-22_faktura-blok-masa.md`,
`2026-07-22_faktura-tabela-citljivost.md`, i ostatak `2026-07-22_*-naimenovanja.md`/
`*-akcija*.md` serije. Merge je bio čist (bez konflikta u `gui/tabs/faktura_view.py`) —
Codexove izmjene su u toolbar/QSS konstrukciji, moje (isti dan) u funkciji
`_run_historical_tariff_validation`/`_update_status_bar`/`_build_analysis_summary_from_draft`
tijelima, bez preklapanja linija.

## 36. PDF dugme — vidljiv indikator padajućeg menija (2026-07-22)

Nakon merge-a (§35), korisnik testirao novu "meni na PDF dugmetu" funkcionalnost (§32-34,
Codex) i primijetio da dugme nema vizuelni signal (mali trokutić) da je padajući meni, ne
obična akcija — `btn_export_pdf.setMenu(...)` postoji u kodu, ali nijedan QSS fajl u
projektu nikad nije definisao `::menu-indicator` (provjereno: `menu-indicator` se ne
pojavljuje nigdje u repou prije ove izmjene), pa se dugme oslanjalo na podrazumijevano
renderovanje stila koje očigledno nije bilo dovoljno vidljivo.

**Fix**: dodato u `styles/button_system.qss` + `dist_client` kopiju — `QPushButton#btnPDF`
dobija `padding-right: 18px` (mjesto za strelicu) i eksplicitan
`QPushButton#btnPDF::menu-indicator` (8×8px, pozicioniran `right center`). Čisto dodatna QSS
izmjena — ne dira Python kod, `_populate_toolbar_section` ni handler funkcije.

## 37. DB čišćenje — obrisano 7 pogrešnih SUSSINA→38249993 zapisa (2026-07-22)

Nastavak §29. Direktnim upitom otkriveno: nije postojao samo 1 sporedni pogrešan zapis nego
**7** (id 62558, 62544, 64709, 64725, 122191, 122192, 122220) — sva "SUSSINA ..." varijanta
imena mapirana na 38249993 umjesto ispravnog 21069098. Tri od njih (122191/122192/122220)
imala su `created_at`/`last_used` iz **2026-07-21/22** (usage_count skočio 2→4) — vjerovatno
posljedica reindeksiranja XML-ova (§27 dopuna 5) koje je vjerno prebrojalo stvarne stare
deklaracije gdje je pogrešan broj bio upisan (korisnikova ranija greška, ne bug u kodu).

**Akcija** (uz eksplicitnu korisničku potvrdu prije DELETE-a — auto-mode klasifikator je
ispravno blokirao prvi pokušaj kao destruktivnu akciju nad produkcijskom bazom): svih 7
redova obrisano ciljano po tačnim `id` vrijednostima (ne widlcard WHERE). Verifikovano:
0 preostalih pogrešnih zapisa, 36 ispravnih (21069098) zapisa netaknuto. Nije bio potreban
kod-nivo fix — ovo je bilo čisto čišćenje podataka, `HistoricalTariffSearchService` već
ispravno bira jači zapis po `usage_count`; problem bi postao vidljiv tek da pogrešan broj
usage_count-om prestigne ispravan (nije bio blizu: 4 vs 40).

## 38. "Provjeri" — selekcija sad skopira i opštu validaciju, ne samo tarifnu (2026-07-22)

Dio "sitnih stvari" iz follow-up liste (§26-31 selekcijski fix je pokrivao SAMO istorijsku
tarifnu provjeru — opšta validacija (brojevi grešaka/upozorenja u sažetku) je i dalje uvijek
prijavljivala stanje SVIH stavki fakture, čak i kad je korisnik selektovao konkretne redove.
`_validation_issue_counts` je HIGH GitNexus impact simbol (27 impactedCount, transitivno kroz
`_update_status_bar` sa ~15 pozivalaca) — plan fajl `project_rooms/
2026-07-22_selekcija-opsta-validacija.md` napisan prije izmjene po AGENTS.md pravilu.

**Fix**: `_validation_issue_counts(self, row_indexes=None)` — novi OPCIONI parametar, default
zadržava identično ponašanje za sve postojeće pozivaoce (svi zovu bez argumenata). U
`_on_validate_all` dodat isti selekcijski obrazac kao u istorijskoj provjeri: bojenje redova
ostaje na SVIM redovima (jeftino, tabela uvijek vizuelno ažurna), ali `error_count`/
`warning_count`/`valid_count`/`total_count` u sažetku i porukama se računaju SAMO za
selektovane redove (direktno preko `validation_cache.get(row)` po indeksu, ne globalni
`get_error_count()`), uz eksplicitnu napomenu u poruci ("Prikazano samo za N selektovanih
stavki"). `auto=True` (puna automatizacija) potpuno netaknuto — selekcija se provjerava samo
kad `not auto`. Testovi: `tests/unit/test_faktura_view_validacija_selekcija.py` (3 nova).

## 39. Transparentnost i za ODBIJENE istorijske prijedloge (2026-07-22)

Posljednja stavka sa "sitnih stvari" liste — simetrično sa `_notify_auto_applied_tariffs`
(§27 dopuna 2, za ranije PRIHVAĆENE prijedloge). `HistoricalTariffSearchService.validate_lines`
je u `feedback_action == "reject"` grani potpuno tiho `continue`-ovala — korisnik nikad nije
vidio DA je prijedlog preskočen niti ZAŠTO (ranija eksplicitna odluka "Odbij" u 'Provjeri').
`validate_lines` — HIGH GitNexus impact (30, transitivno kroz `chat_intent_handler.
_prikaz_tarifnih_trenutnih`) — plan fajl `project_rooms/
2026-07-22_transparentnost-odbijenih-prijedloga.md` napisan prije izmjene; mitigacija: nova
`self.last_auto_rejected` instanca-atributa ne mijenja povratnu vrijednost/potpis metode.

**Fix**: `HistoricalTariffSearchService` dobija `self.last_auto_rejected: list[tuple[int,
str]]` (analogan `last_auto_applied`), popunjava se u reject grani prije `continue`.
`FakturaView._run_historical_tariff_validation` dohvata i remapira indekse (isti obrazac kao
`auto_applied`) i poziva novu `_notify_auto_rejected_tariffs()` kad `not auto` i ima
odbijenih — dijalog navodi Rb./naziv/"bio bi predložen: TARIF" i eksplicitno kaže da je
razlog ranija ručna odluka "Odbij". Generalna "nema boljeg prijedloga" poruka se SUPRIMIRA
kad postoji `auto_rejected` (specifičnija poruka je tačnija i dovoljna). Testovi:
`tests/unit/test_faktura_view_auto_rejected_notice.py` (2 nova), dopune u
`test_faktura_view_provjeri_selekcija.py` (3 nova) i `test_historical_tariff_validation.py`
(dopunjen postojeći test da provjeri `last_auto_rejected`).

## 40. "Pregled po fakturama" PDF fusnota — hardkodovan "(Rb.32)" primjer (2026-07-22)

Korisnik testirao oba nova PDF izvještaja (Codex meni, §32-34) i primijetio da je fusnota
zbunjujuća. Otkriveno: `PDFFakturaPregled.export()` fusnota je od SAMOG POČETNOG commita
(`0149de9`, prije bilo kakvog rada ove sesije ili Codex-a) imala hardkodovan literalni
primjer `"(Rb.32)"` u statičkom objašnjenju kolone "Naimen." — potpuno nepovezan sa stvarnim
podacima deklaracije (samo se slučajno poklopio jer je "32" bio jedan od 40 naimenovanja u
test fakturi). Fix: uklonjen hardkodovan primjer, fusnota sad glasi generički "...pokazuje
redni broj naimenovanja u koje je stavka raspoređena." bez primjera broja.

**Napomena o dva PDF izvještaja** (za razjašnjenje korisnikovog pitanja "ne vidim veliku
razliku"): "Faktura stavke po naimenovanjima" grupiše PO NAIMENOVANJU (tarifna
klasifikacija) — koristan za carinski pregled ("šta je svrstano pod ovu tarifu"). "Pregled
po fakturama" (Codex meni, §32) grupiše PO ORIGINALNOJ FAKTURI dobavljača, sa kolonom
"Naimen." kao referencom, i dodaje PODZBIRIVE po fakturi (Količina/Iznos/Bruto/Neto) i
ukupan zbir cijele deklaracije na kraju — koristan za usaglašavanje sa fakturama dobavljača.
Prvi izvještaj NEMA podzbir po grupi niti ukupan zbir; ovo je namjerna razlika u svrsi, ne
duplikat.

## 41. Oba PDF izvještaja — podzbir po naimenovanju + broj stranice (2026-07-22)

Korisnik zatražio da se realizuju dvije predložene poboljšice iz §40 razgovora.

**Podzbir po naimenovanju** (`PDFInvoiceExporter.export`, "Faktura stavke po naimenovanjima"):
poslije svake tabele naimenovanja dodat red "UKUPNO NAIMENOVANJE N: Količina | Iznos | Bruto
| Neto", i "UKUPNO DEKLARACIJA" na kraju — identičan obrazac kao već postojeći u
`PDFFakturaPregled` (kopiran `_format_float` helper). Sad oba izvještaja imaju konzistentne
zbirove.

**Broj stranice** ("Strana X od Y", oba exportera): dodata `_NumberedCanvas(Canvas)` klasa —
standardni ReportLab dvoprolazni obrazac (broj stranica nepoznat dok se sve ne nacrta, pa se
stanja snime u `showPage()` i broj ucrta tek u `save()`). `doc.build(elements,
canvasmaker=_NumberedCanvas)` umjesto golog `doc.build(elements)`. Fusnota koristi plain
"Helvetica" (nema dijakritika u "Strana X od Y", sigurno bez font-registracije).

**Otkriven propust u testovima (Codex)**: `tests/unit/pdf_invoice_exporter_fonts_test.py` i
`pdf_faktura_pregled_fonts_test.py` NIKAD nisu bili dio standardnog `pytest tests/` sweep-a —
`pyproject.toml` ima `python_files = ["test_*.py"]` (prefiks), a ova dva fajla su imala
sufiks `_test.py`. Testovi su radili SAMO kad se eksplicitno pozovu po putanji fajla (što je
i ovaj i prethodni agent radio, pa se nije primijetilo). Preimenovano u `test_pdf_invoice_
exporter_fonts.py`/`test_pdf_faktura_pregled_fonts.py` (`git mv`, istorija sačuvana) —
potvrđeno: puni suite sad ima 872 passed (859+13, umjesto ranijih 859 koji NIKAD nisu
uključivali ova 13). **Napomena za buduće agente**: pri kreiranju novih test fajlova uvijek
provjeriti da ime počinje sa `test_`, ne završava sa `_test.py` — provjera "testovi prolaze"
je lažno-pozitivna ako se fajl nikad ne kolektuje u punom sweep-u.

Testovi (novi, uz postojećih 9 font testova): `test_export_shows_naimenovanje_subtotal`,
`test_export_shows_page_number` (oba fajla) — svi generišu stvaran PDF i provjeravaju sadržaj
preko pdfplumber-a (isti obrazac kao Codexovi raniji regresioni testovi).

## 42. Inspekcije — istorijska (informativna) napomena iz stvarnih ASYCUDA XML deklaracija (2026-07-22)

Korisnik pokrenuo pitanje: dugme "Inspekcije" u tabu Naimenovanja se oslanja isključivo na
`catalogs.inspection_rules` (statični spisak iz "BiH UIO Objedinjen spisak inspekcijskih
kontrola, mart 2015") koji je zastario i nikad nije bio zvanično ažuriran. Predložio je
učenje iz istorije, po uzoru na tarifno mapiranje.

**Odluka (nakon rasprave)**: NE graditi zamjenski/samostalni sistem — entitetski zakoni o
inspekcijama nisu usaglašeni (samo veterinarska inspekcija je na nivou BiH cijele, ostale su
entitetske), objedinjen spisak ne postoji i vjerovatno nikad neće. Umjesto toga: čisto
**informativni sloj** koji pokazuje "šta se u praksi dešavalo" (koji je dokument stvarno
priložen za taj tarifni broj u prošlim deklaracijama) — **nikad ne mijenja niti suprimira**
pravno pravilo iz `catalogs.inspection_rules`/`InspectionService.check()`. Ista logika kao
GREJAC SPIRALA/Plamenik bug (frekvencija ≠ ispravnost), ovdje opasnija jer je zakonska/
sigurnosna oblast — zato striktno "samo informacija, korisnik odlučuje".

**Izvor podataka**: `H:\New folder\NOVA ASIKUDA` (5706 XML fajlova, autoritativni izvor,
korisnik će ga dalje obogaćivati — VEĆI i BOGATIJI od projektnog `data/knowledge_base/
NOVA ASIKUDA` sa 2503 fajla koji ima samo stare kodove dokumenata).

**Mapiranje kodova priloženih dokumenata (Rub.44) na inspection_type** (potvrđeno od
korisnika — stari trocifreni kod i noviji N-prefiksirani kod su ISTA kategorija):

| Stari kod | Novi kod | inspection_type | Naziv |
|---|---|---|---|
| SAN | N852 | `sanitary` | "Inspekcija za hranu" (preimenovano sa "Sanitarna") |
| VET | N853 | `veterinary` | "Veterinarska inspekcija" |
| FIT | N851 | `phytosanitary` | "Fitosanitarna inspekcija" |
| UVK | N003 | `market_inspection` | "Tržna inspekcija" (NE `quality_control` — moja prvobitna pretpostavka bila pogrešna) |
| AGL | (nema) | `medicines_agency` | "Agencija za lijekove" |

Nema koda za `quality_control` ("Zdravstvena inspekcija") — namjerno bez istorijskog signala.

**Implementacija**:
- `database/migrate_inspection_document_history.py` (nov fajl) — skenira XML arhivu
  (`xml.etree.ElementTree`, `item.findall(".//Attached_documents")`), agregira
  `(tarifni_broj, inspection_type) → usage_count`, gradi `catalogs.inspection_document_history`
  (idempotentno — briše i ponovo gradi cijelu tabelu pri svakom pokretanju, jer arhiva raste).
  Testirano na H: arhivi: 639 parova, npr. `21069098` (SUSSINA tarifa iz §-ova o pogrešnoj
  tarifi) ima sanitary=82, market_inspection=86, veterinary=80, medicines_agency=26 —
  potvrđuje da je podatak stvaran i koristan.
- `InspectionService.historical_hint(tariff_code)` (nova metoda, `services/
  inspection_service.py`) — čita `catalogs.inspection_document_history` po TAČNOM (8-cifrenom)
  tarifnom broju, vraća `list[HistoricalDocumentHint]` (prazno ako nema podatka, BEZ fallback
  nagađanja na prefiks/poglavlje).
- `InspectionDialog._build_historical_note()` (novo, `gui/dialogs/inspection_dialog.py`) —
  po sekciji (tipu inspekcije) prikazuje sivu info-napomenu ("📊 Istorijski podatak
  (informativno, ne zamjenjuje pravno pravilo): tarifni broj(evi) X (Nx), ... — ranije
  zabilježeno u stvarnim deklaracijama") ISPOD postojeće tabele/uslovnog upozorenja — nikad
  ne mijenja boju/status postojećih redova.

**NIJE dirano**: `TariffMappingService.import_from_xml_files` (CRITICAL/`.pyd`-zaključan,
odvojen prolaz kroz XML kako se ne bi dirao taj kod), `catalogs.inspection_rules` i
`InspectionService.check()` (pravno pravilo ostaje netaknuto).

**Status migracije**: pokrenuta 2026-07-23 protiv `H:\New folder\NOVA ASIKUDA` čim je server
postao dostupan — `catalogs.inspection_document_history` sad postoji i popunjena je (639
parova). Uživo potvrđeno za `21069098`: market_inspection=86, sanitary=82, veterinary=80,
medicines_agency=26 (poklapa se sa ranijim probnim skeniranjem). Reimport je idempotentan
(briše i ponovo gradi cijelu tabelu) — ponovo pokrenuti `python database/
migrate_inspection_document_history.py --xml-dir "H:\New folder\NOVA ASIKUDA"` kad korisnik
obogati arhivu novim XML fajlovima. Vidi `project_rooms/2026-07-22_istorijska-napomena-inspekcije.md`
za puni plan.

## 43. Brzo skeniranje uskih grla i dist_client drifta (2026-07-23)

Korisnik zatražio brzo skeniranje poznatih sumnjivih mjesta (uska grla, kompleksan kod)
dok Codex radi na redizajnu. Tri originalna nalaza + dodatni otkriveni tokom istrage:

**1. `TariffMappingService.find_mapping()` — sekvencijalni scan po stavci fakture.**
`_majority_vote()`/fuzzy fallback rade `ILIKE '%riječ%'` upite koji ne mogu koristiti
B-tree indeks. Izmjereno uživo: `EXPLAIN ANALYZE` 49ms po upitu na 25.231 red (Seq Scan),
do 4-5 upita po stavci fakture, bez batchovanja → ~7-12s za fakturu od 50 stavki.
`database/migrations/007_pg_trgm_indices.sql` je već postojao u repou (napisan ranije,
tačno dijagnostikuje ovaj problem) ali **nikad nije bio primijenjen na živu bazu**.
Pokrenut 2026-07-23 — isti upit sad 0.58ms (Bitmap Index Scan, ~84x brže). **Provjeriti
za buduće migracije: postojanje `.sql` fajla u repou ≠ primijenjeno na bazu.**

**2. `dist_client/` vs root drift — kvantifikovano i sanirano.** Bajt-po-bajt poređenje
369 uparenih `.py` fajlova: 45 različitih (12%), od čega ~25 čist BOM/CRLF/trailing-newline
šum, a 20 stvarnih razlika. Od tih 20: nekoliko namjerno različitih (`.pyd` re-export shim
za `tariff_mapping_service.py`, frozen-build DB_PATH patch u `tarifa_service.py`/`run.py`,
`config.py` frozen/bundle path logika, poznat `asycuda_xml_builder.py` print/logger drift
već ranije procijenjen) — te NISU dirane. Sedam bilo je stvarni, ranije neprimijećeni
propusti gdje je root imao fix koji dist_client (shipped runtime) nikad nije dobio:
- `declaration_search_service._flush_batch`: FTS `item_id` bug (`cur.lastrowid` se ne
  ažurira nakon `executemany`) — pretraga bi mogla vratiti podatke pogrešne stavke.
  Root ovo već fiksirao (`agent_reports/2026-07-03_declaration-search-fts-item-id-fix.md`).
- `pdf_faktura_pregled.py`: `draft.sifra_deklaracije` **ne postoji** na `DeclarationDraft`
  modelu (samo `deklaracija_tip`/`deklaracija_oznaka`/`deklaracija_a`) — `AttributeError`
  bi srušio "Pregled po fakturama" PDF u shipped runtimeu. **Aktivan crash bug**, sad fiksiran.
- `pdf_faktura_pregled.py` + `pdf_invoice_exporter.py`: `print()` sa emoji (✅/⚠️/❌) na
  stdout umjesto `logger` — isti obrazac koji je već poznat kao uzrok pada na Windows
  cp1252 konzoli (`feedback_windows_patterns.md`).
- `blagic_attos_importer.py`: bruto/neto težina uvijek iz header-a fakture (uključuje
  ATTOS paletni paušal ~20kg) umjesto iz liste pakovanja kad postoji — netačna deklarisana
  težina u shipped runtimeu. Root već imao fix + test (`test_blagic_attos_pallet_weight.py`).
- `import_worker.py`: nedostajao `"_import_result"` ključ u batch record dictu —
  `faktura_view.py` čita taj ključ za Master Frigo detekciju i header auto-fill, koji su
  u dist_client tiho NIKAD ne okidali (nema exception, samo tiho ne-rade).
- `import_service.py`: Šumaprom CASE 1B/2B `invoice_name` fallback na `filepath.stem`.
- `import_result.py`: nedostajalo upozorenje kad je pronađena samo bruto ili samo neto
  težina (ne oboje).

Također otkriven (ne drift, čist root bug): `processing_worker.py` je imao 5 metoda
(Master Frigo sparivanje) definisano DVAPUT identično u istoj klasi — drugi primjerak
je bio mrtav kod (Python koristi zadnju definiciju). `dist_client` je već bio čist.
Isto za `ocr_utils.py` (`_ocr_cache` deklarisan dvaput).

**3. `system_panel.py._on_ai_health_clicked`** — sinhroni `provider.complete()` na UI
thread-u (samo `setOverrideCursor`, ne sprječava zamrzavanje) — kršilo AGENTS.md pravilo
o QThread za sve LLM pozive. Fix: `_AiHealthCheckWorker(QThread)`.

**Pouka za buduće sesije**: dist_client drift nije samo kozmetički rizik — ovaj put je
sadržavao aktivan crash bug (AttributeError) i netačnu deklarisanu težinu (pravni rizik).
Vrijedi periodično ponoviti bajt-po-bajt poređenje (skripta u ovoj sesiji, ~15 linija
Pythona) umjesto čekanja da korisnik prijavi bug specifično na Windows/shipped build.

Commitovi: `eacf3d5` (cleanup dupliciran kod), `b2648f2` (dist_client mirror fixevi),
`fc08233` (AI health check QThread). Puni test suite: 915 passed nakon svih izmjena
(isti pre-postojeći 3 fail/1 error nepovezani sa ovim radom).

## 44. "no such table: tarifa_2026" — pretraga trgovačkih naziva u Šifarnicima (2026-07-23)

Korisnik prijavio grešku u Šifarnici tabu (numerička pretraga tarifnog koda) uz sumnju da je
Codex-ov redizajn tog taba nešto pokvario. **Provjereno: `gui/tabs/sifarnici/tariff_hierarchy.py`
je bit-za-bit identičan u root-u, `dist_client/` i Codex-ovoj radnoj grani** — Codex NIJE uzrok.

**Pravi uzrok**: `_DB_PATH` u `tariff_hierarchy.py` računat je fiksnom relativnom putanjom od
`__file__` (`../../../database/deklarant_sistem.db`). U PyInstaller frozen buildu `__file__`
pokazuje unutar `_internal/` bundle-a, dok stvarna (read-write) `deklarant_sistem.db` živi
POKRAJ `.exe`-a — ta baza NIJE u `deklarant_pro.spec` `datas` listi (bundluju se samo
`zvanicna_tarifa.db` i `inspection_rules.db`, read-only referentni podaci). Kad izračunata
putanja ne postoji, `sqlite3.connect()` **tiho napravi NOVU praznu bazu** na toj putanji —
upit na `tarifa_2026` onda puca sa "no such table" jer ta nova baza nema nijednu tabelu.

Isti obrazac buga (i isto rješenje) već postoji u `services/tariff/tarifa_service.py::
_resolve_db_path()` — lista kandidata (standardna dev putanja → frozen exe-folder putanja →
CWD-relativna) umjesto jedne fiksne putanje. Primijenjen isti pristup u `tariff_hierarchy.py`.

**Pouka**: kad god modul računa putanju do `database/*.db` preko `os.path.dirname(__file__)`
bez `sys.frozen` provjere, provjeriti da li ta baza uopšte postoji u `deklarant_pro.spec`
`datas` listi — ako ne postoji (jer je read-write/lokalna), fiksna `__file__`-relativna
putanja će raditi u dev modu ali tiho pucati u frozen `.exe`-u. Vidi i `config/settings.py`
(PROJECT_ROOT vs BUNDLE_ROOT) za opšti obrazac.

Testovi (novi): `test_tariff_hierarchy_db_path.py` — standardna putanja, frozen fallback na
exe folder, fallback kad ništa ne postoji (3 testa, monkeypatch `sys.frozen`/`sys.executable`).

Commit: `29f3015`.

## 45. Sistematsko traganje za istom klasom buga + jos 3 pg_trgm indeksa (2026-07-23)

Nakon §44, korisnik zatražio da se ista klasa bugova sistematski potraži kroz cijelu
kodnu bazu (150k+ linija) — tri ciljane, jeftine provjere umjesto opšteg pregleda:

**a) Isti `__file__`-relativni DB_PATH bez `sys.frozen` svijesti** — grep otkrio JOŠ DVA
pogođena runtime modula (ne migracioni/admin skriptovi, koji su van scope-a jer se ne
pokreću iz shipped `.exe`-a):
- `services/tariff/tariff_tree_service.py` — **gori nego prvobitni bug**: broj `..` u
  putanji je bio pogrešan (jedan umjesto dva), pa je putanja bila netačna **čak i u dev
  modu** (rešavala se u `services/database/` koji ne postoji). Vjerovatno ostatak kad je
  fajl premješten iz `services/tariff_tree_service.py` (postoji i taj, kao re-export shim)
  u podfolder `services/tariff/`, bez ažuriranja broja `..`. Koristi ga agent chat
  "pretraži tarifu hijerarhijski" (`chat_intent_handler.py`) — tiho je vraćalo prazne
  rezultate (uhvaćeno u `try/except`, bez vidljive greške korisniku).
- `services/agent/chat/tariff_history_analysis_service.py` — putanja tačna u dev modu,
  ali bez frozen-build fallback-a (isti rizik kao `tarifa_2026` bug iz §44). Koristi ga
  agent chat "analiziraj tarifne historiju".

Oba popravljena istim `_resolve_db_path()` obrascem (kandidati + frozen fallback na exe
folder) kao `tariff_hierarchy.py` iz §44. 5 novih testova. Commit `577a3b7`.

**b) AST provjera dupliciranih metoda/funkcija** (isti obrazac kao `processing_worker.py`
bug iz §43) — **čist rezultat**: nula pogodaka u projektnom kodu (`services/`, `gui/`,
`importers/`, `core/`, `database/`, `exporters/`, `scripts/`, `config/`, `dist_client/`
sopstveni izvor, `app/`, root `.py` fajlovi). Jedina 2 pogotka bila su u
`dist_client/.venv/site-packages/` (vendorisane biblioteke `protobuf`/`openpyxl`) — nisu
naš kod. **Zaključak**: `processing_worker.py` je bio izolovan slučaj, ne sistemski
obrazac — nema potrebe za daljom akcijom.

**c) ILIKE upiti bez pg_trgm indeksa** (isti obrazac kao `product_tariff_mapping` iz §43)
— grep 30 ILIKE poziva u `services/`, provjerene tabele po veličini. Tri dodatne tabele
potvrđene kao Seq Scan preko `EXPLAIN ANALYZE`:
- `catalogs.product_similarity_memory` (26.404 reda, "slični proizvodi" agent analiza) —
  postojao je B-tree `idx_product_similarity_supplier` koji NE pomaže ILIKE-u — 76ms → 0.88ms
- `catalogs.zvanicna_tarifa` (12.686 redova, "Trgovački nazivi" pretraga) — 38.6ms → 0.69ms
- `catalogs.declaration_items` (9.798 redova) — postojao `idx_items_naziv_robe_fts` (FTS
  `@@` operator, DRUGI tip indeksa od ILIKE-ovog `~~*`) — 25.5ms → 0.44ms

Male referentne tabele (`izvoznici` 2116, `uvoznici` 678, `drzave` 249,
`carinski_postupci` 148 redova) namjerno preskočene — seq scan na tako malim tabelama je
već sub-milisekundni, dodatni indeks ne bi donio mjerljivu korist. Migracije 011, 012
(primijenjene na živu bazu + mirrovane u `dist_client/database/migrations/`). Commit `004b67f`.

**Pouka**: sve tri ciljane provjere potvrđuju da je "nađi jedan primjer buga, pa provjeri
da li postoji ista klasa na drugim mjestima" produktivnija strategija od opšteg code review-a
— (a) i (c) su odmah dale dodatne, stvarne pogotke, dok je (b) dala koristan NEGATIVAN
rezultat (potvrda da nešto NIJE sistemski problem, ne samo "nije nađeno jer se nije tražilo
dovoljno dobro").

## 46. Dodatne frozen DB putanje i exception-safe Qt bulk popunjavanje (2026-07-24)

Read-write SQLite baze u frozen buildu moraju imati prioritetnu putanju
`Path(sys.executable).parent / "database"`, prije bilo koje `__file__` lokacije iz
`_internal` direktorija. Samo postojanje `_internal/database` direktorija nije dokaz da
je u njemu prava upisiva baza. Ovo je primijenjeno na `llm_audit_log.py` i
`tariff_doc_history_service.py`, uz ciljane frozen-path testove.

Pri bulk popunjavanju Qt tabela nije dovoljno pozvati `blockSignals(True)` i na kraju
ručno vratiti `False`. Sačuvati prethodna stanja `signalsBlocked`, `updatesEnabled` i,
gdje postoji, `isSortingEnabled`, pa ih vratiti u `finally` bloku. Tako se ne narušava
stanje koje je pozivalac već postavio i tabela ne ostaje zamrznuta nakon izuzetka.

## 47. MCP dijakritička pretraga i uklanjanje re-export shimova (2026-07-24)

MCP historical search ne zavisi od PostgreSQL `unaccent` ekstenzije. Umjesto toga,
`mcp_server/tools/search_helpers.py::searchable_patterns()` gradi parametrizovane regex
pattern-e za domaća slova (`c/č/ć`, `s/š`, `z/ž`, `d/đ`, `dj/đ`) i koristi PostgreSQL
`~*` operator. Ovo zadržava deploy bez dodatnih DB privilegija, ali mijenja query plan
u odnosu na `ILIKE`; kod velikih tabela ponovo provjeriti performanse prije širenja
pattern-a.

Top-level re-export shimovi u `services/`, `services/agent/` i `importers/` su uklonjeni
tek nakon migracije internih pozivalaca na stvarne pakete (`services.agent.learning.*`,
`services.agent.chat.*`, `services.tariff.*`, `importers.vendors.*`). Izuzetak: u
`dist_client` postoji namjerni `.pyd` most za `services.tariff_mapping_service`; fajl
`dist_client/services/tariff/tariff_mapping_service.py` ne treba mehanički prepisivati
na self-import niti brisati bez rebuilda runtime paketa.

## 48. Performansni DB audit — carinski_dokumenti FTS indeks (2026-07-24)

Nakon Pi agent nalaza o ILIKE/FTS performansama provjeren je live PostgreSQL. Trigram
indeksi iz §45 su već prisutni i koriste se na velikim tabelama
(`product_tariff_mapping`, `product_similarity_memory`, `zvanicna_tarifa`,
`declaration_items`). Preostali nedostatak bio je `ix_carinski_dokumenti_fts` na
`catalogs.carinski_dokumenti`, iako migracioni fajl već sadrži `CREATE INDEX`.

Uzrok: `database/migrate_carinski_dokumenti.py` je poslije SQL-a radio `print()` sa emoji
znakom. Na Windows konzoli sa cp1252 kodnom stranicom to baca `UnicodeEncodeError` prije
izlaska iz `with psycopg2.connect(...)` bloka, pa se transakcija može rollbackovati i indeks
ne ostane kreiran. Migracija zato mora imati ASCII-safe završni ispis. Tabela trenutno ima
samo 28 redova, pa PostgreSQL normalno bira Seq Scan i nakon indeksa; forsirani plan
(`SET LOCAL enable_seqscan = off`) potvrđuje da je GIN indeks upotrebljiv.

## 49. Jedinstveni import workflow — korekcije Faza 2-4 (2026-07-24)

Neutralni import workflow prije UI integracije mora tretirati `consumed_paths` i
parserov `is_combined=True` kao jedini autoritativni dokaz da su dva fizička fajla
jedna logička faktura. Isti `invoice_number` sam po sebi nije dovoljan za sabiranje
stavki i težina; drugi isti broj u batchu ide kao `DraftOperation.SKIP` dok korisnik
ili budući servis primjene ne odluči drugačije.

`services.import_workflow.prepare_service` koristi isključivo
`services.faktura.weight_guards.normalize_invoice_key` za poređenje faktura, jer crtice
u broju fakture moraju ostati semantički značajne kao u postojećem Faktura toku.
Prepare faza radi na kopijama `InvoiceLine` objekata i ne smije mutirati parser/agent
izvorne rezultate prije korisničke potvrde.

Korisničke odluke u Fazi 4 su obavezno vezane za `invoice_key`: `ABORT` za partner ili
valutu prekida cijeli plan, `SKIP_INVOICE` izbacuje samo tu fakturu, a
`DraftOperation.SKIP` se nikad ne smije pojaviti u listi faktura za primjenu.

## 50. Jedinstveni import workflow — Faza 5 atomska primjena (2026-07-24)

`services.import_workflow.apply_service.apply_import_plan()` je jedini servisni ulaz za
konačnu primjenu pripremljenog plana na `DeclarationDraft`. Servis ne otvara Qt dijaloge,
ne osvježava tabelu i ne poziva Agent chat; prima već prikupljene `UserDecisions` i koristi
`invoices_to_apply()` kao jedini filter korisničkih odluka.

Rollback je servisni: prije izmjene se uzima snapshot svih draft polja osim callback liste,
a neočekivana greška vraća `invoice_lines`, `invoice_weights`, `source_files`, `warnings`,
header i `dirty` stanje. GUI Undo tačka nije dio Faze 5 jer nema neutralnog Undo managera;
controller je dodaje u Fazama 6-8 prije poziva servisa.

Faza 5 primjenjuje povlastice samo iz eksplicitnog `OriginDialogResponse.dialog_data`
(`povlastica`/`preference_code`, `eur1_number`, `zemlja_porijekla` i flags). Ako je origin
dijalog preskočen, Rub.36 se ne mijenja i servis ne izmišlja povlasticu.

## 51. Jedinstveni import workflow — Faza 6 ručni pojedinačni import (2026-07-24)

Obični ručni pojedinačni `ImportResult` u `FakturaView._on_import_finished()` sada ide
kroz zajednički tok `from_import_result()` → `prepare_import()` → UI odluke →
`apply_import_plan()`. Stari `_on_import_finished` ostaje kao `_on_import_finished_legacy`
fallback za list-import/backward-compat i za Assembly/Master-list tok, jer faza 5 servis
još ne pokriva `DeclarationAssembly.add_invoice()` matching.

PE2/PE3/EUR1 dijalozi se i dalje prikazuju u View sloju, ali se njihovi podaci više ne
primjenjuju direktno na `draft.invoice_lines` u novom običnom toku. View skuplja
`OriginDialogResponse`, a `apply_service` razumije postojeći format dijaloga po zemlji/grupi
(`items`, `preference`, `invoice_number`, `eur1_number`, `code`) i primjenjuje ga na kopije
stavki tokom atomske primjene. Ovo je važno za fakture sa više zemalja porijekla; ne vraćati
na flat povlasticu za cijelu fakturu.

## 52. Jedinstveni import workflow — Faza 7 Agent import (2026-07-24)

Agent ruta `AgentController._on_all_completed()` više ne smije ručno čistiti
`draft.invoice_lines` po svakom fizičkom fajlu niti zasebno imitirati logiku
`FakturaView`. Nakon faze 7 Agent za modove "Uvezi u deklaraciju" i
"Puna automatizacija" koristi isti neutralni tok kao ručni import:
`from_file_item()` → `prepare_import()` → UI odluke → `apply_import_plan()`.

To znači da Agent i ručni import sada dijele istu politiku za normalizaciju tarifa,
ADD/REPLACE/SKIP odluku, provjeru partnera/valute, raspodjelu bruto/neto masa,
dodjelu `invoice_number` i primjenu PE2/PE3/EUR1 podataka. Agent-specifično ostaje
samo kanal prikaza rezultata (chat aktivnosti/poruke), prebacivanje na Faktura tab,
poziv historijske provjere nakon uvoza i dodatni EUR1 follow-up prema naimenovanjima.

Kod budućih izmjena ne vraćati logiku importa u per-file petlju Agent controllera.
Nova pravila se dodaju u `services.import_workflow.*`, a Agent smije samo prikupiti
korisničke odluke i prikazati rezultat.

## 53. Jedinstveni import workflow — završne faze batch/runtime (2026-07-24)

Ručni grupni import `FakturaView._process_batch_records()` sada koristi isti neutralni
workflow kao pojedinačni ručni import i Agent import: batch record → `ImportCandidate`
→ `prepare_import()` → UI odluke → `apply_import_plan()`. Time su normalizacija tarifa,
ADD/REPLACE/SKIP, partner/valuta konflikt, raspodjela masa, header i PE2/PE3/EUR1 odluke
zajedničke za sva tri aktivna ulaza.

Legacy batch tok ostaje namjerno kao `_process_batch_records_legacy()` samo kada je
`assembly.master_list_loaded=True`, jer Assembly/Master-list režim i dalje ima posebnu
logiku koja nije dio neutralnog draft apply servisa. Isto važi za `_on_import_finished_legacy()`
kod pojedinačnog importa. Ne brisati ove fallback-e dok poseban Assembly tok ne bude
eksplicitno pokriven servisom i testovima.

`_expected_import_partners()` mora ignorisati ne-string vrijednosti (npr. test/mock objekte)
prije poređenja partnera. U suprotnom `prepare_import()` može dobiti objekat umjesto teksta
i pasti u `normalize_partner_name()`.

`dist_client` je usklađen ručno samo za runtime import workflow promjene. Ne poravnavati
cijeli `dist_client/gui/tabs/faktura_view.py` sa root fajlom jer postoje starije namjerne
UI razlike iz redizajna.
---

## 54. Inline validacija GUI obrazaca (2026-07-23)

Postojeći modali ostaju autoritativni za završne i blokirajuće provjere; inline
oznake služe samo da korisnika odvedu do mjesta greške. Faktura označava
konkretnu tarifnu ili zemlja ćeliju, Naimenovanja status vodi do prvog
neispravnog polja, Zaglavlje modal nudi „Prikaži polje“, a Šifrarnici fokusiraju
prvo prazno obavezno polje. Ove oznake ne smiju mijenjati poslovna pravila,
draft podatke ni raspored tabova.

---

## 55. Standard tastaturne navigacije (2026-07-23)

Glavne kartice koriste `Ctrl+1`–`Ctrl+6`; `Ctrl+Tab`/`Shift+Ctrl+Tab` ostaju
standardni Qt tok. Tamo gdje postoji prethodni/sljedeći zapis koriste se
`Alt+Left/Right` i opcioni gaming aliasi `Alt+A/D`. Obični `W/A/S/D` i obične
strelice se nikad globalno ne presreću jer pripadaju unosu teksta, tabelama i
combo poljima. `F6` ulazi u gornji toolbar aktivne kartice; tek kada dugme ima
fokus, `Left/Right` ili `A/D` mijenjaju dugme, a `Esc` vraća prethodni fokus.
Zaglavlje ima eksplicitan fokusni lanac kroz `field_widgets`.

## 56. Standard hover stanja dugmadi (2026-07-23)

Aktivna `QPushButton` i `QToolButton` dugmad koriste akcentni obrub `#F2C14E`
uz promjenu semantičke nijanse. Normalno stanje ima transparentan obrub iste
debljine, pa hover ne smije mijenjati geometriju, padding niti položaj teksta.
Onemogućena dugmad ne dobijaju hover akcenat.

## 57. E2E provjera jedinstvenog import workflow-a sa stvarnim fakturama (2026-07-25)

Nakon §49-53 (jedinstveni import workflow, Codex/Pi), izvještaji su eksplicitno
ostavili "potrebna ručna GUI provjera sa stvarnim fajlovima iz `najavauvoza/`"
kao otvoren rizik. Umjesto GUI-ja (headless nemoguć), napravljen je direktan
servisni e2e test: `ImportService.import_file()` → `from_import_result()` →
`prepare_import()` → `apply_import_plan()`, sa PE/EUR1 dijalog odgovorima
simuliranim kao `SKIPPED`. Novi trajni test:
`tests/integration/test_real_invoice_import_e2e.py` (graciozno se preskače
ako arhiva faktura nije dostupna — `DEKLARANT_INVOICE_DIR` / `H:\New folder\
najavauvoza` / korisnički `Downloads`).

**Potvrđeno na 4 stvarna vendor formata** (Master Frigo, PIP Food, SRECKO,
Medicopharm) — svi scenariji koje su izvještaji označili kao nepotvrđene:
- Jedan uvoz: ispravne stavke/težine/iznos (Master Frigo 51 stavka = 22.813,00
  EUR, poklapa se sa imenom fajla)
- **REPLACE na ponovni uvoz iste fakture** (ne duplikat) — VAŽNO: `existing_
  invoice_keys` MORA se graditi identično kao `FakturaView.
  _existing_invoice_keys_for_import_workflow()` (iz `invoice_number` polja
  stavki + `draft.invoice_weights` ključeva, NE iz `invoice_name`) — prvi
  pokušaj testa je pogrešno koristio `invoice_name` i lažno pokazao duplikat
- Konflikt partnera se detektuje kad se uveze faktura različitog izvoznika
  u draft koji već ima drugog (ne miješa se tiho)
- Kombinovani uvoz (faktura+packing) postavlja `consumed_paths`, bez duplih
  stavki

**Medicopharm 1476/26** (94 stavke, 22.662,72 EUR, bruto 310/neto 284.94 —
sve iz zbirnog sažetka na samoj fakturi, zlatni standard) je otkrio DVA
stvarna buga u toku dubljeg testiranja (oba popravljena, oba imaju testove):

1. **`ImportService._normalize_tariffs_in_result()`** je `zfill(8)`-om lijevo
   dopunjavao SVAKI 4-7-cifreni tarifni broj — ispravno samo za slučaj
   "izostavljena vodeća nula poglavlja 01-09", pogrešno za sve ostalo. Rb.78:
   `"3304990"` (7 cifara, poglavlje 33 kozmetika, izostavljena ZADNJA cifra)
   → tiho postajalo `"03304990"` (nepostojeće poglavlje 03 riba). Odluka
   (potvrđena od korisnika): auto-dopuna je UKLONJENA za cijeli 4-7 opseg —
   `declaration_validator_service.py` već baca ERROR za tarifu koja ne
   postoji u zvaničnoj tarifi, pa nepotpun kod dobija vidljivo upozorenje
   umjesto tihe fabrikacije. HIGH GitNexus impact (univerzalna funkcija, svi
   import putevi) — plan u `project_rooms/2026-07-25_ukloni-lijevu-dopunu-
   kratkih-tarifa.md`.
2. **Medicopharm razdvaja istu 8-cifrenu tarifu po zemlji porijekla** dodatnim
   brojčanim sufiksom (npr. `"330499000080"` = tarifa `33049900` + sufiks
   `0080` za Veliku Britaniju) — korisnikovo objašnjenje, potvrđeno testom da
   aplikacija ionako postiže isti razdvoj kroz 4-ključno grupisanje
   naimenovanja (tarifa+zemlja+povlastica+eur1), sufiks je za njih interno
   knjigovodstvo. Taj sufiks je obično slijepljen uz tarifu, ali je na ovoj
   fakturi (Rb.93) razdvojen razmakom (`"33051000 0000"`) — `_try_parse_
   item_line()` ga je ubacivao kao prvu riječ naziva robe. Fix: čisto
   brojčani token odmah iza tarife se preskače (potvrđeno da nijedan
   legitiman naziv na fakturi ne počinje brojem).

**Pouka**: i "gotov, testovima pokriven" refaktoring može sakrivati domenske
edge-case bugove koji se pojave samo na stvarnim, "ružnim" podacima (razmak
umjesto slijepljenog sufiksa, faktura sa sopstvenim tipfelerom u tarifi) —
sintetički testni podaci ih ne bi otkrili. Vrijedi periodično ponoviti e2e
provjeru sa novim stvarnim fakturama, ne samo jednom.

Commitovi: `ed8f219` (e2e test), `db7f05d` (fix zfill), `dd136aa` (fix
Medicopharm sufiks). Pun test suite: 1103 passed nakon svih izmjena (isti
pre-postojeći 1 fail/1 error nepovezani sa ovim radom).

**Dodatak — pregled paralelnog Pi izvještaja** (`agent_reports/2026-07-25_
istraga-naimenovanja-faktura-tok.md`, nezavisna istraga Naimenovanja/Faktura
tabova): dva nalaza označena "KRITIČNO", oba provjerena PRIJE bilo kakvog
djelovanja (ne uzeti tuđi izvještaj zdravo za gotovo, isti standard kao za
sopstvene nalaze):
- **§1a ("dist_client i dalje ima zfill(8) bug")** — **zastario nalaz**,
  generisan prije commita `db7f05d` koji je već mirrovao fix u oba fajla.
  Provjereno uživo (diff root/dist_client identičan). Nije popravljano jer
  nije ni bilo pokvareno.
- **§1b (`FakturaView._get_tariff_description` — `__file__` bez
  `sys.frozen`)** — **potvrđen stvaran, četvrti primjer iste klase buga**
  (§44/45), i gori od ranijih: eksplicitno provjerava `db_path.exists()` i
  ODMAH odustaje (prazan opis) bez pokušaja alternativne putanje. Popravljeno
  ponovnom upotrebom već frozen-svjesnog `_DB_PATH` iz `tariff_hierarchy.py`
  umjesto dupliranja `_resolve_db_path()` po peti put. Commit `89f54bb`.

Ostatak Pi izvještaja (arhitekturni dug — Naimenovanja bez Controller sloja,
N+1 upiti u petljama, QThread `cancel()` nedostaje za ChatWorker/
TariffLLMWorker, itd.) nije provjeravan niti primjenjivan u ovoj sesiji —
ostaje kao katalog za buduć rad, ne provjereno sam ako je svaki navod tačan.

## 58. Codex analiza Faktura taba — 4 popravljena buga (2026-07-25)

`Downloads/Codex-analiza-faktura-taba.docx` (Codex audit + ChatGPT dodatak)
je prvo verifikovan navod-po-navod protiv stvarnog koda (12+ tvrdnji,
SVE potvrđene tačne, neke gore nego opisano) prije bilo kakve izmjene.
Popravljeno je 6 nalaza niskog rizika, namjerno OSTAVLJENO netaknuto sve
arhitekturno (QUndoStack redesign, FakturaController ekstrakcija,
revision-tracking, puni ExportPreflightService, PDF document-context
cache, DB connection pooling) — korisnikov zahtjev je bio "popravi sve što
možeš ali budi oprezan", ne redizajn.

**Popravljeno** (svi imaju testove ili su verifikovani py_compile + pun
test suite):

1. **Dupli red pri "Dodaj" + nedostajući undo** (`_on_add_item`,
   `faktura_view.py`) — `_add_item_to_table()` sama radi `insertRow()` na
   osnovu trenutnog `rowCount()`; pozivalac je PRIJE toga i sam radio
   `insertRow()` → jedan prazan + jedan popunjen red za jednu novu stavku.
   Fix: pozivalac više ne radi vlastiti `insertRow()`, plus dodan
   `_push_undo_snapshot()` koji je potpuno nedostajao (Ctrl+Z nije
   poništavao ručno dodatu stavku).
2. **Toolbar trajno onemogućen nakon uvoza** (`_on_import_finished`) — tri
   rane `return` grane (prazan plan, korisnik odustao, apply neuspio)
   izlazile su PRIJE `self._set_buttons_enabled(True)`, ostavljajući
   dugmad zaključana do restarta taba. Fix: premješteno u `finally` blok
   uz `_cleanup_import_worker()`.
3. **"Očisti sve" ne čisti `invoice_weights`/`source_files`**
   (`_on_clear_all`) — `draft.invoice_lines.clear()` je čistio stavke, ali
   `invoice_weights` je zadržavao stare ključeve po broju fakture → sljedeći
   uvoz "nove" fakture sa istim brojem se pogrešno tretirao kao REPLACE
   postojeće umjesto novog uvoza u prazan draft. `draft.items`
   (naimenovanja) namjerno NIJE očišćen — to je vidljiv korisnički sadržaj,
   rizičnije za tiho brisanje; staleness tu rješava nalaz #6 ispod.
4. **Naivni `_parse_number()`** — bezuslovno je brisao SVE tačke kao
   hiljadarke prije provjere zareza: `"1234.56"` (čist decimalni zapis, bez
   zareza) → `"123456"` → `123456.0` umjesto `1234.56`. Fix: delegira na
   susjednu, već ispravnu `_parse_weight_input()` koja auto-detektuje EU/US
   format po poziciji ZADNJEG separatora — striktno poboljšanje, isti
   rezultat za sve ispravne unose, ispravan rezultat za bug-slučaj.
5. **`TariffProposal` identitet kolidira po `line_no` kroz više faktura**
   (`services/tariff/tariff_mapping_service.py`) — svaki importer numeriše
   `line_no` od 1 PO FAKTURI. "Auto-popuni" bez selekcije (default tok) radi
   nad CIJELIM `draft.invoice_lines` odjednom — `commit_proposals()` je
   uparivao prijedlog isključivo po `line_no`, pa su dvije stavke iz
   različitih faktura sa istim rednim brojem kolizijom dobijale POGREŠAN
   tarifni prijedlog jedna umjesto druge. Fix: dodano `TariffProposal.
   line_index` (pozicija u listi, iz `enumerate()`), `commit_proposals()`
   uparuje prioritetno po njemu; ručno sastavljeni proposali bez
   `line_index` (postojeći test) i dalje rade preko `line_no` fallback-a.
   **NIJE mirrorano u `dist_client`** — taj modul je tamo Nuitka `.pyd`
   (`tariff_mapping_service.cp314-win_amd64.pyd`, kompajliran 2026-07-18),
   fix je samo u ROOT izvoru (koji `.exe` build koristi direktno preko
   `deklarant_pro.spec`); dist_client runtime treba rebuild pri sljedećem
   Windows deploy-u da pokupi ovaj fix.
6. **`fill_basic_fields()` mutira prije undo snapshot-a** (`_on_auto_fill`)
   — mutacija se dešavala ODMAH, prije preview dijaloga i prije eventualnog
   otkazivanja; "Otkaži" u dijalogu je ostavljao neundo-vateljivu mutaciju.
   Fix: `_push_undo_snapshot()` premješten prije `fill_basic_fields()` poziva
   (uklonjen duplikat sa stare pozicije).
7. **Excel export tiho izostavlja stavke bez naimenovanja** (`_on_export_
   excel`) — `ExportService.export_to_excel()` grupiše isključivo po
   `assigned_naimenovanje_ordinal > 0`, stavke bez dodijeljenog naimenovanja
   nestaju iz fajla bez ikakve poruke. Fix: preflight provjera u GUI sloju
   (ne u `ExportService` — namjerno mala izmjena, ne puni
   `ExportPreflightService`) koja broji i upozorava korisnika PRIJE izvoza,
   uz mogućnost nastavka.

**Usput otkriven i popravljen NEPOVEZAN test regres**: `tests/unit/
test_faktura_view_tariff_description_db_path.py` je pisan za raniju
implementaciju `_get_tariff_description` (direktan sqlite3 + `_DB_PATH`,
§57/commit `89f54bb`). Međuvremeni refaktor (commit `703a68e`, "ujednači
opise tarife u TariffService sa cache-om, N+1 fix") je delegirao logiku na
`TariffService.load_hierarchical_label` i keširao instancu na `self.
_tariff_desc_service` — test je od tog commita tiho pucao jer `object()`
kao lažni `self` ne dozvoljava postavljanje atributa (AttributeError se
hvata u `except Exception`, vraća se sam tarifni kod kao "opis", test
tvrdi suprotno). Nije bug u produkcionom kodu (pravi `FakturaView` je
`QWidget`, podržava atribute normalno) — samo test-fixture nekompatibilnost
sa novijom implementacijom. Fix: lagani `_FakeSelf` stub umjesto `object()`.
Usput uklonjen i mrtav/nedostižan drugi `except Exception:` blok u
`_get_tariff_description` (ostatak istog refaktora, oba root i dist_client).

Pun test suite nakon svih izmjena: 1128 passed (isti pre-postojeći 1
fail/1 error, oba nepovezana — hardkodovana lična putanja u `test_xml_
parser_fix.py`, nedostajuća fixture u `test_model_benchmark.py`).

Commitovi: `3ce36de` (faktura_view.py 4 fixa), `6b6aa3c` (TariffProposal
line_index), `5538265` (test fix).

## 59. HistoricalValidationWorker — istorijska validacija tarifa u pozadini (2026-07-25)

Nastavak §58 — Codex nalaz "performanse" (`_run_historical_tariff_validation`
blokira UI) i Pi-jeva istraga (`agent_reports/2026-07-25_istraga-
naimenovanja-faktura-tok.md`, nalaz 2b) nezavisno prijavili isti bug:
`HistoricalTariffSearchService.validate_lines()` (DB upit po stavci) se
pozivao sinhrono na UI threadu, poslije SVAKOG importa (5 poziva u
`faktura_view.py`) — UI se zamrzavao za vrijeme trajanja upita. Pi je taj
nalaz eksplicitno ostavio neriješenim ("Srednji rizik — zahtijeva novi
QThread worker + testiranje sa stvarnim DB", `agent_reports/2026-07-25_
popravke-naimenovanja-faktura.md`), preporučio ga kao sljedeći korak.

**Implementacija**: novi `HistoricalValidationWorker(QThread)` u `services/
historical_validation_worker.py` — isti `cancel()`/`_cancelled` obrazac kao
`ProcessingWorker`/`TariffLLMWorker`, konstruiše PRIVATNU
`HistoricalTariffSearchService()` instancu u `run()` (ne singleton — isti
razlog kao `ProcessingWorker`: izbjegavanje race condition-a između thread-
ova), emituje `finished_validation(matches, auto_applied, auto_rejected)`
kad DB upit završi.

`_run_historical_tariff_validation` je podijeljen na dva dijela:
- Dispatch (glavni thread, nepromijenjena logika selekcije redova) —
  konstruiše i pokreće worker
- `_on_historical_validation_finished` (novi slot, glavni thread) —
  SADRŽAJNO NEIZMIJENJENA logika remapiranja indeksa/upisa u tabelu/
  dijaloga, samo premještena iz stare sinhrone funkcije

**Staleness guard** (dva nezavisna tokena, oba moraju odgovarati da bi se
rezultat primijenio):
- `_historical_validation_token` — inkrementiše se pri SVAKOM dispatchu;
  odbacuje rezultat starijeg workera ako je u međuvremenu pokrenut noviji
  poziv (npr. dva brza klika na "Provjeri")
- `_validation_generation` (već postojeći brojač iz `_load_data_from_draft`,
  vidi §nepoznat/postojeći kod) — odbacuje rezultat ako je draft reload-ovan
  (delete/clear/import-replace) dok je worker radio, sprječavajući upis u
  red koji se u međuvremenu pomjerio na drugu poziciju

Namjerno KONZERVATIVNO: kod mismatch-a bilo kojeg tokena, rezultat se
POTPUNO odbacuje (nema pokušaja remapiranja indeksa) — sigurnije nego
pokušati pogoditi novu poziciju stavke.

**MainWindow._shutdown_agent_workers** (eac0b3d obrazac) proširen da gasi
i ovaj worker — `_shutdown_worker()` izdvojen kao static helper, poziva se
za Agent tab worker I za `faktura_tab.view.historical_validation_worker`.

**Testovi**: `tests/unit/test_historical_validation_worker.py` (novi, 6
testova — worker emisija/greška/cancel preko `qtbot.waitSignal`, staleness
guard, shutdown oba workera). `tests/unit/test_faktura_view_provjeri_
selekcija.py` (postojećih 11 testova ažurirano na dvoslojnu arhitekturu —
`worker.start()` patchovan na no-op za dispatch-testove, `_on_historical_
validation_finished` testiran direktno za remapiranje/notifikacije — ista
pokrivenost, bez čekanja na pravi QThread).

Pun test suite: 1135 passed (isti pre-postojeći 1 fail/1 error,
nepovezani). GitNexus `detect_changes`: risk LOW, 0 affected_processes.

Commit: `b9594fb`.

## 60. Podjela po zemljama u status baru — nedostajala kod ručnog uvoza (2026-07-25)

Korisnička prijava (screenshot statusne trake): ručni uvoz fakture nema
"🌍 DE:54 | FR:24 | ..." podjelu po zemljama kao agentski uvoz (ne treba
mješati sa "Assembly: N/A" — TO je odvojen, nepovezan indikator za
master-list feature, `self.assembly.master_list_loaded`).

**Uzrok**: `lbl_analysis` segment se prikazuje samo ako je `self.
_analysis_summary_auto == True` (`_refresh_analysis_summary_from_draft`
inače rano izlazi). Taj flag je postavljala ISKLJUČIVO `AgentController.
_proactive_analysis()` preko `fw.set_analysis_summary(...)`
(`gui/tabs/agent/agent_controller.py:743`) — poziva se SAMO nakon Agent
uvoza. Ručni uvoz (`_on_import_finished` i varijante) nikad nije postavljao
ovaj flag, pa segment nikad nije prikazan za ručni tok.

**Fix**: `_update_status_bar()` sad jednosmjerno uključuje
`_analysis_summary_auto` čim ima bar jedna stavka u draftu (bilo kojim
putem — ne samo Agent uvozom). Prikazani tekst i dalje računa POSTOJEĆA,
ispravnija `_build_analysis_summary_from_draft()` (čita trenutno stanje
tabele/drafta, normalizuje zemlju na 2-slovni kod) — `AgentController`
poziv ostaje netaknut, samo postaje redundantan (flag je već True do tada).

GitNexus impact na `_update_status_bar` je HIGH (30 pogođenih, 21 direktan
pozivalac) — funkcija je centralni hub, ne zato što je izmjena rizična.
Plan zapisan u `project_rooms/2026-07-25_analiza-summary-rucni-uvoz.md`
prije izmjene (AGENTS.md HIGH-risk protokol); `detect_changes()` poslije
potvrdio LOW (izmjena aditivna, 2 linije, ne dira postojeću logiku).

Pun test suite: 1138 passed (+3 nova regresiona testa u `tests/unit/
test_faktura_view_status_bar.py`).

Commit: `bf99ef2`.

## 61. Data Boundary propust u ChatWorker Zone B2 (2026-07-25)

Korisnik je donio prijedlog "Kontrolisana podatkovna granica za AI agente"
(allowlist umjesto blocklist, AgentSafeInput schema, cloud vs lokalni model
razlika) i tražio poređenje sa stvarnim stanjem aplikacije. Nalaz: `services/
agent/chat/audit_log.py`, `tool_policy.py` i `ChatWorker._allow_sensitive_
data()` VEĆ implementiraju sličnu filozofiju (audit log eksplicitno ne čuva
sadržaj faktura/API ključeve, `TOOL_EFFECTS` je fail-closed whitelist,
`_allow_sensitive_data()` FORSIRA maskiranje čak i kad je `SEND_SENSITIVE_
DATA=true` ako je aktivni provider cloud — jače od onoga što dokument
predlaže). `product_similarity_embedding_service.py` koristi isti env flag
za embedding — potvrđuje da je ovo ustaljena, cross-cutting politika.

**Stvaran propust otkriven poređenjem**: `ChatWorker._build_session_zone()`
(Zone B) maskira `izvoznik_naziv`/`primalac_naziv` kad `_allow_sensitive_
data()` vrati False. `_build_zaglavlje_zone()` (Zone B2, dodaje se u ISTI
`_build_context()` payload odmah nakon Zone B) je slala ista polja PLUS
`deklarant_naziv` bez ikakve provjere — maskiranje iz Zone B je bilo
efektivno zaobiđeno (partner imena su stizala do cloud LLM-a i sa default,
"bezbjednim" podešavanjem). Uzrok: Zone B2 je vjerovatno dodata kasnije
("polja koja agent nije vidio") bez revizije postojeće maskirajuće politike
iz Zone B — tačan obrazac koji dokument opisuje u §5 (blocklist/allowlist
per-zona lako zaboravi novu vrstu osjetljivog polja kad se zona doda).

Fix: `_build_zaglavlje_zone()` sad koristi isti `_allow_sensitive_data()`
gate za sva tri partner-imena polja. GitNexus impact LOW na funkciju (1
direktan pozivalac), `detect_changes()` poslije MEDIUM (2 affected_processes,
oba tačno "Run → _build_zaglavlje_zone" — očekivano, bez iznenađenja).

**Šta iz dokumenta NIJE prisutno** (razlika u pristupu, ne nužno propust):
formalna Pydantic schema (kontekst se gradi kao slobodan tekst, ne
validirana struktura — uzrok gornjeg propusta: svaka zona ima svoju ad-hoc
logiku umjesto jedne centralne provjere), forbidden-marker testovi (§12,
ne postoji test koji ubaci lažni marker i provjeri da ne procuri u
kontekst/log/agent_report), "Data Boundary" sekcija u agent_report
template-u.

Pun test suite: 1134 passed (novi 3 testa u `tests/unit/test_chat_worker_
zaglavlje_zone_masking.py`), + 10 DB-backed testova (`test_decision_
characterization.py`) privremeno failed zbog nedostupnosti PostgreSQL
servera (192.168.100.154 timeout) — nepovezano sa ovom izmjenom,
infrastrukturni problem, ne regres.

Commit: `223d543`. Plan za Pydantic AgentSafeInput schemu (sljedeći korak,
zaseban zadatak): `project_rooms/2026-07-25_agent-safe-input-schema-plan.md`.

## 62. Faza 1 AgentSafeContext schema + AgentContextAdapter (2026-07-25)

Prva faza plana iz §61 (`project_rooms/2026-07-25_agent-safe-input-schema-
plan.md`). Korisnik potvrdio: Rb.44 (brojevi priloženih isprava) NISU
osjetljivi, ne treba ih maskirati — schema ih uključuje bez ograničenja.

Novi, izolovani fajlovi (ChatWorker NIJE mijenjan — to je Faza 2, zaseban
zadatak):

- `services/agent/chat/safe_context_schema.py` — Pydantic modeli:
  `DraftSummary`, `PartnerInfo` (name=None kad je maskirano), `AttachedDocument`,
  `DeclarationHeaderSummary`, `AgentSafeContext`.
- `services/agent/chat/context_adapter.py` — `AgentContextAdapter`:
  `build_partner_info()` (jedina tačka maskiranja partner imena),
  `build_draft_summary()`, `build_header()` — preslikavaju TAČNU postojeću
  logiku iz `ChatWorker` Zone A/B/B2 (ista formula za bez_tarife/bez_zemlje/
  sa_povlasticom/ceka_eur1, ista formula za zemlja_distribucija), spremni
  za direktnu zamjenu u Fazi 2 bez promjene ponašanja.

GitNexus `detect_changes(scope=staged)` prije commita: risk LOW, 0
affected — nove datoteke bez ijednog postojećeg pozivaoca, tačno kako Faza
1 plan predviđa (izolovano, nula rizika za postojeći kod).

8 novih testova (`tests/unit/test_agent_context_adapter.py`) — maskiranje
partnera (uključeno/isključeno/prazna imena), tačnost agregata, `None`
draft edge case, priložene isprave bez maskiranja, Pydantic validacija
(negativan broj stavki odbijen).

Pun test suite: 1139 passed (+8). Isti poznati DB nedostupnost (server
192.168.100.154, korisnik potvrdio: dostupan sutra ujutru — 10 DB-backed
testova u `test_decision_characterization.py` ostaju failed do tada, nije
regres) + 1 pre-postojeći nepovezan fail.

Commit: `4eb88d0`. **Faza 2 (migracija ChatWorker Zone B/B2 da koriste
adapter) NIJE urađena** — čeka zaseban zadatak/odluku o obimu (Faza 4 vs
5, `TariffLLMWorker` migracija, prioritet — vidi otvorena pitanja u
project_room planu).

## 63. Faze 2-5 dovršene — AgentSafeContext migracija (2026-07-26)

Nastavak §62 — korisnik potvrdio nastavak do Faze 5 (implicitno odgovara
na plan §7 pitanje "Faza 4 vs 5").

**Faza 2** (`d737a90`) — `_build_session_zone` (Zone B) i `_build_zaglavlje_
zone` (Zone B2) migrirani na novi `AgentContextAdapter.mask_partner(role,
name)` — jedina tačka odluke o maskiranju, umjesto ručnog `if send_
sensitive:` po polju u svakoj zoni (tačan obrazac koji je uzrokovao §61
propust). Ponašanje provjereno IDENTIČNO original logici za sve slučajeve
(uključujući "JIB postoji, ime ne" ivicu u Zone B). Zone B ranije NIJE
imala test koji provjerava stvaran sadržaj — dodano 5 novih testova; JIB
DB upit (`find_xml_for_pair`, PostgreSQL) mockovan u testovima da ne čekaju
DB timeout (87s → 0.9s).

**Faza 3** (`0aa54d4`) — Zone A (`=== STANJE DRAFTA ===`) agregati
(ukupno/bez_tarife/bez_zemlje/sa_povlasticom/ceka_eur1/zemlja_distribucija)
migrirani na `AgentContextAdapter.build_draft_summary()`. `bez_tarife_
list`/`bez_zemlje_list` (liste REDOVA, ne brojevi) ostaju lokalni jer ih
koriste kasnije sekcije. **GitNexus impact HIGH** (6 affected_processes,
`_build_context` je centralna orkestracija) — prijavljeno korisniku prije
commita po AGENTS.md protokolu; verifikovano ponašanje-identično (2 nova
testa + 31/31 postojećih `test_tool_use_offline.py` testova nepromijenjeno).

**Faza 4** (`5b8bd16`) — ostatak Zone B2 (valuta/iznos/kurs, uslovi
isporuke, vid transporta, država izvoza, troškovi, priložene isprave)
migriran na `AgentContextAdapter.build_header()`. Usput otkriven i
ispravljen razmak-propust u vlastitom Faza 1 kodu (`vid_transporta` imao
jedan razmak umjesto dva prije "granica=") — uhvaćen testom prije nego što
je Faza 4 stvarno oživjela taj kod u produkciji. 6 novih testova.

**Faza 5** (`c12d451`) — analizirane preostale zone (`_build_knowledge_
zone`, `_build_tariff_validation_context`, `_search_declarations_context`):
- `_build_knowledge_zone`/`_build_tariff_validation_context` NE diraju
  partner podatke (samo tarifni kodovi/nazivi robe/zemlje) — **namjerno
  NISU migrirane** (migracija bi bila čist code churn bez sigurnosne
  koristi).
- `_search_pg_partners` je već ispravno maskiran. `docs/deklarant_pro_
  code_review.md` §2.2 i `docs/deklarant_pro_analiza_i_prijedlozi.md` §1.2
  tvrde suprotno ("ignoriše SEND_SENSITIVE_DATA") — **verifikovano
  ZASTARJELO** (opisuju stariju verziju koda), docs NISU ažurirani (van
  scope-a). Nema akcije jer nije pokvareno.
- `_search_declarations_context` "Pretraga po partneru" grana **JE
  migrirana** — isti ranjivi obrazac (ručni ternary po polju) kao Zone B2.
  2 nova testa.
- **Otvoreno pitanje, namjerno NEDIRANO**: ista grana pokazuje STVARAN JIB
  kad je `send_sensitive=True` (za razliku od Zone B gdje se JIB NIKAD ne
  šalje LLM-u bez obzira na flag) — dokumentovano komentarom u kodu, čeka
  korisničku potvrdu da li je namjeravana razlika.

**Forbidden-marker test** (`6a93455`, plan §8) — `tests/unit/test_chat_
worker_forbidden_markers.py`: ubaci prepoznatljive markere u SVA partner
polja (oba izvora — Zone B invoice_lines[].exporter.name I Zone B2 draft
Zaglavlje polja), provjeri da se nijedan ne pojavi u cjelokupnom
`_build_context()` outputu kad je maskiranje uključeno; kontrolni test
(sensitive=True) potvrđuje test nije lažno pozitivan.

Pun test suite: 1156 passed (bilo 1139 prije Faze 2, +17 novih testova
kroz sve faze). Isti pre-postojeći DB nedostupnost (server dostupan od
2026-07-26 ujutru po ranijoj korisničkoj potvrdi) + 1 nepovezan fail.

Faze 1-5 kompletne. `TariffLLMWorker` migracija i `header_attached_
documents` (već uključeno, potvrđeno neosjetljivo u §60) van scope-a —
nema više otvorenih faza iz plana.

## 64. DB grešku ne miješati sa "nema istorijskog prijedloga" (2026-07-26)

**Live debug sesija**: korisnik pokrenuo aplikaciju, uvezao fakturu 1476/26
(Medikopharm), selektovao stavku "SUSSINA 650 tbl." (tarifa 38249993 iz
fakture) i kliknuo "Provjeri" — dobio "nema boljeg istorijskog prijedloga"
iako je (po korisnikovom znanju) postojao bolji prijedlog.

**Uzrok**: PostgreSQL server je bio na DHCP-u premješten (treći put u ovoj
sesiji — sada na `192.168.0.25`, `.env`/`dist_client/.env` ažurirani,
van gita po `.gitignore`). `HistoricalTariffSearchService._search_one()`
je hvatao SVAKI izuzetak (uključujući DB konekcijsku grešku) i tiho vraćao
`[]` — identično ponašanju "provjereno, stvarno nema prijedloga". Nakon
popravke IP-a, direktna provjera je potvrdila: 15 istorijskih zapisa za
"SUSSINA" postoji (`catalogs.product_tariff_mapping`, mapiraju na
`21069098`), a `validate_lines()` sad ispravno vraća jak prijedlog
(usage_count=43) sa ranijom "accept" povratnom informacijom (auto-primjena).

**Fix**: `HistoricalTariffSearchService.last_db_error` — postavlja se u
`_search_one()` SAMO za `psycopg2.Error` (DB konekcija/timeout/circuit
breaker), resetuje na početku svakog `validate_lines()` poziva. Ne-DB
izuzeci i dalje se tiho gutaju (nepromijenjeno ponašanje).
`HistoricalValidationWorker` provjerava `last_db_error` nakon
`validate_lines()` — ako postavljen, emituje `error_occurred` umjesto
`finished_validation` (sprječava lažno-uspješan prikaz praznog rezultata).
`FakturaView._on_historical_validation_error` sad prima `auto` flag i
prikazuje `QMessageBox.warning` kad NIJE auto mod — ranije je greška
SAMO logovana, korisnik nije vidio ništa čak ni kod stvarne DB greške.

GitNexus impact na `validate_lines` je HIGH (22 impactedCount, 6 direktnih
pozivalaca uključujući Agent chat tool i `scripts/agent_tariff_eval_
report.py`) — namjerno **aditivan** dizajn (novi atribut, ne mijenja
postojeći povratni tip/ugovor) drži stvaran rizik nizak uprkos GitNexus
ocjeni; nijedan postojeći pozivalac nije morao biti mijenjan.

Usput instaliran OCR (`pytesseract`, `pdf2image`, `opencv-python` preko
pip; sistemski Tesseract 5.4.0 preko `winget install UB-Mannheim.
TesseractOCR` — aplikacija ga već auto-detektuje preko `importers/pdf/
ocr_utils.py::_find_tesseract()`, bez potrebe za PATH izmjenom).

9 novih/proširenih testova. Pun test suite: 1174 passed (DB-backed testovi
iz `test_decision_characterization.py` sad prolaze — server dostupan),
isti 1 nepovezan pre-postojeći fail.

Commit: `db3ca95`.

## 65. Politika: istorijski prijedlog bez potvrđenog izvora se NIKAD ne prikazuje (2026-07-26)

Nastavak live debug sesije (§64) — korisnik je u `TariffValidationDialog`
vidio prijedloge sa oznakom "izvor nepoznat" (prazna ili placeholder
`supplier`/`source` kolona: `"-"`, `"+"`, `"A"`, `"HISTORIJA"`). Sistem je
VEĆ sprečavao bulk auto-prihvatanje takvih prijedloga (`_can_accept_all`),
ali ih je i dalje prikazivao za pojedinačnu potvrdu — konkretno, "ista
tarifna glava" grana u `decide_tariff_match()` je UVIJEK vraćala
`SHOW_WEAK` bez ikakve provjere izvora ili učestalosti korištenja.

**Korisnička odluka** (eksplicitno obrazloženje): pogrešna carinska tarifa
nosi stvaran rizik sankcija/kazni — nepotvrđen izvor mapiranja nije
dovoljan dokaz čak ni za informativan prijedlog koji traži ručnu potvrdu.

**Fix**: `decide_tariff_match()` sad vraća `SUPPRESS` ODMAH čim izvor nije
poznat (`has_meaningful_source() == False`), prije bilo koje druge provjere
(tarifna glava, poglavlje, usage_count).

**POLITIKA-OBRTAJ vrijedan pažnje**: ovo direktno poništava odluku iz
2026-07-22 (SUSSINA fix, docstring u `_search_one()`) koja je NAMJERNO
propuštala zapise sa visokim usage_count ali bez dobavljača — obrazloženje
tada je bilo "ne gubi jak istorijski signal". Današnja odluka eksplicitno
prioritizuje "nikad pogrešna preporuka" nad tim. **Posljedica**: zapisi sa
VISOKIM usage_count ali BEZ ikad zabilježenog izvora (česti kod starijih,
"zlatnih" naučenih mapiranja iz perioda prije striktnog praćenja izvora)
se sada NIKAD ne prikazuju, čak ni kao slab prijedlog. Jedini način da se
takav zapis ponovo pojavi je popuniti `supplier`/`source` kolonu u
`catalogs.product_tariff_mapping` za taj zapis (ručna ili skriptovana
podatkovna korekcija, van scope-a ovog fixa).

GitNexus impact na `decide_tariff_match` (upstream) je HIGH (11 pogođenih,
3 direktna pozivaoca — Faktura tab "Provjeri", Agent chat tarifni alat,
offline eval skripta) — prijavljeno korisniku prije nastavka po AGENTS.md
protokolu. `detect_changes` (staged) poslije potvrdio LOW/0 affected —
ostali pozivaoci ispravno propagiraju SUPPRESS preko postojećeg
`should_show` ugovora bez potrebe za izmjenom.

Testovi: 1 nov eksplicitan test (`test_unknown_source_never_shown_
regardless_of_usage_or_heading`) + 3 postojeća ažurirana (jedan testira
evidence klasifikaciju direktno jer suprimiran match više ne stiže do
`validate_lines()` izlaza; jedan dobio stvaran izvor da ne bude zbunjen
novom politikom; SUSSINA-bez-dobavljača test preimenovan i dokumentuje
politiku-obrtaj) + `tariff_validation_cases.json` fixture (2 "is_shown"
slučaja sa praznim izvorom → "without_source_is_suppressed", + 2 nova
"with_source_is_shown" para da se očuva pokrivenost "show" putanje).

Pun test suite: 1177 passed, isti 1 nepovezan pre-postojeći fail.

Commit: `5a53d08`.

### §66 — JIB u partner-search grani usklađen sa Zone B pravilom (2026-07-26)

Follow-up na §62-63 (AgentSafeContext migracija) — otvoreno pitanje iz
Faze 5 sad zatvoreno korisničkom odlukom.

**Prije**: `_search_declarations_context` (partner-search grana,
`chat_worker.py`) je pokazivala STVARAN `consignee_jib` LLM-u kad
`_allow_sensitive_data()` vrati `True` (tj. `SEND_SENSITIVE_DATA=true` I
lokalni provider — cloud provideri se već forsirano maskiraju). Zone B
(`_build_session_zone`) nikad ne šalje JIB LLM-u, bez ikakvog uslova.

**Korisnička odluka**: uskladiti sa Zone B — JIB se NIKAD ne šalje LLM-u
ni u jednoj grani, čak ni uz eksplicitni `SEND_SENSITIVE_DATA=true` opt-in
na lokalnom modelu. Jedno apsolutno pravilo umjesto uslovnog izuzetka.

**Fix**: `jib_display` u partner-search grani je sad uvijek
`"[JIB skriven]"`, bez obzira na `send_sensitive`. Ime izvoznika/primaoca
i dalje idu kroz `AgentContextAdapter.mask_partner()` (nepromijenjeno) —
samo JIB polje je zaključano.

GitNexus impact na `_search_declarations_context` (upstream) je LOW (2
pogođena simbola, `_build_context`→`run`, 1 proces). `detect_changes(all)`
poslije potvrdio LOW/0 affected processes.

Testovi: docstring u
`test_chat_worker_declarations_partner_search_masking.py` ažuriran (više
nije "namjerno nedirano"), dodan nov test
`test_partner_search_jib_nikad_ne_ide_u_kontekst` koji provjerava da pravi
JIB nikad ne uđe u kontekst, za oba stanja `send_sensitive`.

Commit: vidi `agent_reports/2026-07-26_jib-partner-search-usklajivanje.md`.

### §67 — Opis tarife u dijalogu "Automatski ažurirane tarife" (2026-07-26)

Korisnička primjedba (uz screenshot poređenje dva dijaloga): dijalog
"Potvrda auto-popunjavanja tarifnih brojeva" (`_show_tariff_preview_dialog`,
prikazuje PRIJEDLOGE prije upisa) ima tabelu sa kolonom "Opis tarife" —
korisnik odmah vidi šta novi tarifni broj znači. Dijalog "Automatski
ažurirane tarife (ranija potvrda)" (`_notify_auto_applied_tariffs`,
prikazuje tarife koje su VEĆ upisane zbog ranije ručne potvrde) je bio goli
tekst `Rb.X: naziv → tarifa`, bez opisa — deklarant je opis morao sam
tražiti u tarifniku/PDF-u/šifarniku, što remeti radni tok.

**Fix**: izdvojena zajednička tabela `_build_tariff_table_widget()`
(Rb/Naziv/Tarifa/Izvor/Opis, ista stilizacija) — koristi je i
`_show_tariff_preview_dialog` (refaktorisan, bez promjene ponašanja) i nov
`_show_tariff_table_info_dialog()` (OK-only varijanta, bez Potvrdi/Odustani
jer je tarifa već primijenjena). `_notify_auto_applied_tariffs` sad gradi
`rows` sa `opis=self._get_tariff_description(tarif)` i zove novi dijalog.
Izvor je labelovan "Ranija ručna potvrda (100%)".

`_notify_auto_rejected_tariffs` (simetrični dijalog za ODBIJENE prijedloge)
je NAMJERNO ostavljen kako jeste — van scope-a ove primjedbe, nema
promjene tarife pa opis nove tarife nije od direktne koristi tamo
(follow-up ako korisnik zatraži isto).

GitNexus impact: `_notify_auto_applied_tariffs` upstream LOW (7 impacted, 1
direktan pozivalac), `_show_tariff_preview_dialog` upstream LOW (1 direktan
pozivalac `_on_auto_fill`). `detect_changes(all)` poslije potvrdio LOW/0
affected_processes — samo "touched" na `FakturaView` metodama u istom
fajlu (+ mirror u `dist_client/gui/tabs/faktura_view.py`, koji je bio
bajt-identičan prije izmjene pa je primijenjen identičan diff).

Testovi: `test_faktura_view_auto_applied_notice.py` ažuriran da provjerava
poziv `_show_tariff_table_info_dialog` sa `rows` (dict lista) umjesto
starog `_show_scrollable_info_dialog` teksta, uklj. eksplicitnu provjeru da
`_get_tariff_description` biva pozvan sa tačnim tarifnim kodom. Pun test
suite: 1178 passed, isti 1 nepovezan pre-postojeći fail
(`test_xml_parser_fix.py`, hardkodovan Linux path) + 1 nepovezan error
(`test_model_benchmark.py`, fixture `model_name` ne postoji) — oba
pre-postojeća, nevezana za ovu izmjenu.

### §68 — Dugme "Podešavanja" u Admin → Baza podataka (2026-07-26)

Korisnička primjedba (screenshot Admin panela): "u admin panelu imamo
mogućnost da se ručno klikne na spoji ali nema podešavanja?" — status
konekcije i "Testiraj konekciju" postoje u `DatabasePanel`
(`gui/tabs/admin/panels/database_panel.py`), ali host/port/baza/korisnik/
lozinka se čitaju JEDNOM iz `.env` pri konstrukciji panela
(`config.settings.get_db_settings()`) i nigdje se ne mogu editovati iz
aplikacije — jedini put je ručno uređivanje `.env` fajla.

**Otkriveno usput**: `gui/dialogs/db_setup_dialog.py` (`DbSetupDialog`) je
POTPUNO gotov ekran za baš ovu namjenu — host/port/ime baze/korisnik/
lozinka, test konekcije u pozadinskom threadu, snimanje u `.env` — sa
docstringom koji kaže "Prikazuje se kad... konekcija na bazu ne uspije" i
čak gotovom `check_and_setup_db(app)` helper funkcijom namijenjenom pozivu
iz `run.py` pri startu. Nijedno od toga nije nigdje pozvano u aplikaciji
(potvrđeno grep-om) — isti obrazac "sagrađeno pa nikad povezano".

**Fix**: dodato dugme "Podešavanja" pored "Testiraj konekciju" u
`DatabasePanel` (`_on_settings()`), koje otvara postojeći `DbSetupDialog`
(već ima `_load_existing_env()` — predpopuni iz `.env` automatski). Nakon
potvrde (`Accepted`): poziva se `_reload_settings()` iz istog modula (isti
mehanizam koji `check_and_setup_db()` koristi pri startu — resetuje
`config.settings._db_settings` singleton i zatvara stari
`database.db._connection_pool`, bez toga bi promjena ostala nevidljiva do
restarta aplikacije), zatim se osvježi `lbl_server` prikaz i automatski
ponovo pokrene test konekcije.

**Napomena korisnika**: DHCP promjena IP-a servera (viđeno 3x u sesiji
2026-07-25/26 — `.55`→`.25`→`.154`→`.25`) će biti trajno riješena kad se
serveru dodijeli statična adresa na mreži — ovo dugme je i dalje korisno
nezavisno od toga (promjena baze/korisnika/porta bez ručnog `.env`
uređivanja), ali ne zamjenjuje taj follow-up. Startup auto-provjera
konekcije (razgovarano u istoj sesiji, ista `DbSetupDialog`/
`check_and_setup_db()` infrastruktura) NIJE urađena u ovom koraku —
korisnik je eksplicitno odgodio do static IP-a.

GitNexus impact na `DatabasePanel` (upstream): LOW (8 impacted, samo
import lanac kroz `admin_view.py`→`admin_controller.py`/`admin_tab.py`
→`main_window.py`, 0 affected_processes). `detect_changes(all)` poslije
potvrdio LOW/0 affected_processes.

Testovi: nov `test_database_panel_settings_button.py` (2 testa — potvrda
otvara dialog/reload/re-test, otkazivanje ne radi ništa), isti MagicMock
"self" obrazac kao `test_faktura_view_auto_applied_notice.py`. Dodatno
offscreen konstrukcija stvarnog `DatabasePanel` widgeta (Qt
`QT_QPA_PLATFORM=offscreen`) da se potvrdi da grid layout raspored (2
dugmeta umjesto 1 koje je spanning) ne puca. Pun test suite: 1180 passed,
ista 2 pre-postojeća nepovezana problema.

`dist_client/gui/tabs/admin/panels/database_panel.py` mirror bio
bajt-identičan prije izmjene — primijenjen identičan diff.
`gui/dialogs/db_setup_dialog.py` NIJE mijenjan (već identičan u oba
stabla) — samo povezan, ne izmijenjen.

### §69 — Boja dugmadi u DbSetupDialog (2026-07-26)

Korisnik je uživo isprobao dugme "Podešavanja" iz §68 i poslao screenshot:
"Testiraj konekciju" dugme nevidljivo (bijela slova na svijetloj
pozadini), dok je "Snimi i nastavi" ispravno vidljivo (sivi tekst na
sivoj pozadini, disabled stanje).

**Uzrok**: `_btn_test` u `DbSetupDialog._build_ui()` nije imao lokalni
`setStyleSheet()` — oslanjao se na globalni app QSS
(`styles/unified_color_system.qss`, `QPushButton { background-color:
#3D6A8A; color: #FFFFFF; }`, učitava se u `MainWindow.load_stylesheet()`).
`_btn_save` JE imao eksplicitan lokalni stylesheet i renderovao se
ispravno. U praksi se globalni QSS za ovaj dugme u ovom modalnom dijalogu
NIJE primjenjivao vidljivo (razlog nije do kraja utvrđen — kaskada preko
9 QSS fajlova je teška za potpunu ručnu analizu — ali dokaz da isti obrazac
"eksplicitan lokalni stylesheet" već radi za susjedno dugme u ISTOM
dijalogu je bio dovoljan za pragmatičan fix, bez potrebe da se do kraja
razriješi zašto globalna kaskada ovdje ne radi).

**Fix**: oba dugmeta (`_btn_test`, `_btn_save`) sad dijele identičan
eksplicitan stylesheet (plava `#2980b9`/bijeli tekst kad je enabled, sivo
`#bdc3c7`/`#7f8c8d` kad je disabled, hover `#3498db`) — garantovano
vidljivo bez obzira na globalnu kaskadu, i vizuelno konzistentno unutar
istog dijaloga (korisnički zahtjev: "u skladu sa drugim dugmadima, mislim
na boju").

**Usputni nalaz (nije popravljen, samo zabilježen)**: `app/run.py::main()`
POSTOJI kao alternativni entry point koji VEĆ poziva
`check_and_setup_db()` (startup DB provjera + setup dialog) — ali
PyInstaller spec (`deklarant_pro.spec:137`) gradi `dist_client`/produkciju
iz `run.py` (root), NE iz `app/run.py`. `app/run.py::main()` je dostupan
samo preko `__main__.py`→`app/__init__.py` (npr. `python -m` poziv), što
NIJE isti kod-put kao stvarni `.exe`. Ovo znači da je startup auto-provjera
tehnički već napisana negdje u repou, ali je mrtav kod za produkcioni
build — potvrđuje raniju procjenu (§67/razgovor 2026-07-26 prije §68) da
stvarna aplikacija nema startup DB provjeru. Follow-up ako se ikad odluči
implementirati startup provjeru: razmotriti da li samo pozvati
`check_and_setup_db()` iz `run.py::main()`, umjesto duplicirati logiku.

GitNexus impact: `DbSetupDialog` upstream LOW (20 impacted, samo import
lanci, 0 affected_processes). `detect_changes(all)` poslije potvrdio
LOW/0 affected_processes.

Testovi: nov `test_db_setup_dialog_button_visibility.py` — potvrđuje oba
dugmeta imaju POSTAVLJEN i MEĐUSOBNO IDENTIČAN stylesheet (regresiona
zaštita, ne testira stvaran render/pixel). Pun test suite: 1181 passed,
ista 2 pre-postojeća nepovezana problema.

`dist_client/gui/dialogs/db_setup_dialog.py` mirror bio bajt-identičan
prije izmjene — primijenjen identičan diff.

---

## 69. Agent routing — dokazani uzroci zamjene prikaza i provjere (2026-07-26)

Analiza za redizajn `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` (v2.0).
Pet nalaza koji se NE vide iz čitanja pojedinačnog fajla:

**1. Ista keyword tabela postoji na dva nivoa.** `_application_context_scope()`
(`gui/tabs/agent/services/chat_intent_handler.py:760`) i `route_local_tool()`
(`services/agent/chat/tool_dispatcher.py:63`) donose istu odluku "koja poruka je
snapshot". Popravka jednog NE popravlja drugi.

**2. `tool_definitions.py` sam uči LLM pogrešno mapiranje.** Opis alata
`prikazi_naimenovanja` (linija 172-175) doslovno kaže "Koristi za 'pregledaj
naimenovanja'", a SYSTEM_PROMPT pravilo 17 (linija 38) mapira "pogledaj tab
faktura" na `pregled_stanja_aplikacije`. Bilo kakav popravak intent routinga
mora obuhvatiti i ovaj fajl, inače LLM grana ostaje pokvarena.

**3. Mrtva grana.** U `_handle_message`, `_application_context_scope()` (linija
1024) presreće PRIJE `_is_naimenovanja_review_request()` (linija 1030) i vraća
`return`. Zato je `_is_naimenovanja_validation_request` — funkcija napisana
tačno da razlikuje prikaz od provjere — nedostižna za "pregledaj naimenovanja".
Dodatno, u `_application_context_scope:781` provjera `faktura` ide prije
`naimenov`, pa "pregledaj naimenovanja iz fakture" vraća `faktura`.
Pouka: prije popravke routing grane provjeriti da li je uopšte dostižna.

**4. `_puna_auto_pipeline` je vezan za UI thread i re-entrantan.**
`QApplication.processEvents()` između faza + `QMessageBox.question()` inline +
pozivi `fw._on_*` GUI metoda. Posljedica: korisnik može kliknuti drugu radnju
usred pipeline-a (nema brave). Premještanje u servisni sloj NIJE premještanje
koda nego inverzija zavisnosti.

**5. `core/draft/` nema `revision`/`fingerprint`/`__hash__`.** Svaki mehanizam
tipa "provjera više ne važi jer se draft promijenio" mora ga prvo uvesti.

**Konkurentne reprezentacije ishoda validacije: osam.** `ValidationResult`
(validation_service **i** preference_validator — različite klase, isto ime),
`ValidationItem`/`ValidationReport`, `Issue`/`ComplianceResult`,
`NaimenovanjeValidation`, `PipelineStageResult`, `ToolResult`,
`overall_outcome()`. Ime `ValidationError` postoji na pet mjesta (jednom kao
dataclass, četiri puta kao izuzetak). Svaki novi adapter MORA uvoziti sa
aliasom, inače dobije pogrešnu klasu bez greške pri importu.

**Imena alata moraju biti ASCII** (`^[a-z0-9_]{1,64}$`) — Groq/OpenAI
function-name shema odbija dijakritiku, pa npr. `provjeri_usklađenost_tabova`
ne bi radilo.

---

### §70 — Auto-detekcija pariteta isporuke (Incoterms) iz faktura (2026-07-26)

Korisnički zahtjev: Rb.20 "Uslovi isporuke" u Zaglavlju se nikad nije
popunjavao automatski — korisnik je paritet (EXW/FCA/FAS/FOB/CFR/CIF/CPT/
CIP/DAP/DPU/DDP) uvijek unosio ručno, iako se pojavljuje kao prepoznatljiv
tekst na fakturama. Otkriveno usput: KG Fashion i Master Frigo importeri
su VEĆ imali regex za paritet ("paritetu: XXX", "Paritet isporuke: XXX"),
ali vrijednost se gubila prije nego stigne do `ImportResult`/drafta —
parsirano pa odbačeno.

Korisnička odluka (eksplicitno obrazložena — paritet je pravno obavezan
podatak u carinjenju, mora se tražiti i "u parserima koje imamo i koje
ćemo eventualno graditi"): samo šifra pariteta (ne i mjesto isporuke —
previše rizično parsirati iz slobodnog teksta), kroz SVE importere,
uključujući buduće. Ako se ne pronađe pouzdano, polje ostaje prazno za
ručni unos — nikad pogrešan pogodak (isti princip kao §65
izvor-nepoznat-nikad-prikazan).

**Arhitektura — plan revidiran tokom rada.** Prvobitna ideja (analogna
`_normalize_tariffs_in_result()` u `ImportService` — centralna post-
processing funkcija) odbačena nakon istrage: sirovi tekst fakture postoji
samo kao efemerna lokalna varijabla UNUTAR svakog parsera (`full_text`),
nikad ne izlazi u `ImportResult`. Centralna varijanta bi zahtijevala DVA
nova polja (`raw_text` + `incoterm_code`) na `ImportResult` (već CRITICAL-
impact klasa) i izmjenu u `ImportService`. Umjesto toga — isti stil kao
već postojeće `consumed_paths` pravilo: svaki importer sam poziva
zajedničku `detect_incoterm()` funkciju i prosljeđuje REZULTAT (ne sirovi
tekst) kao `incoterm_code=...`. Jedno novo polje, bez izmjene
`ImportService`.

**Šta je urađeno:**
1. `importers/incoterm_utils.py` (nov) — `detect_incoterm(text) -> str`.
   Samo label+kod obrasci (regex: "Incoterms[2020]?", "Paritet\w*[
   isporuke]?", "Uslovi isporuke", "Delivery terms?", "Termin isporuke" +
   jedan od 11 važećih kodova), NAMJERNO bez blind standalone pretrage
   koda bez konteksta (izbjegava lažne pozitive — carinski rizik).
2. `importers/import_result.py` — dodato `incoterm_code: str = ""`.
3. Povezano kroz **12 importer fajlova**: `generic_pdf_importer.py`
   (default/fallback parser), `kg_fashion_importer.py` i
   `master_frigo_importer.py` (zamijenjen lokalni regex zajedničkom
   funkcijom — single source of truth), `medicopharm_importer.py`,
   `sumaprom_pdf_parser.py` + `sumaprom_combined_importer.py` (excel-only
   dio nema tekst, preskočen), `leburic_pekabesko_pdf_parser.py` +
   `leburic_pekabesko_importer.py` (`_extract_from_pdf` tuple proširen
   4→5 elemenata), `pip_food_parser.py`, `cmana_pdf_parser.py`
   (docstring firme već pominjao "način isporuke" u footeru — potvrda da
   se paritet stvarno pojavljuje na ovim fakturama), `imamoglu_pdf_parser.py`,
   `blagic_loren_pdf_parser.py` + `blagic_loren_importer.py`
   (`_find_and_extract_weights_from_pdf` tuple proširen 2→3) +
   `blagic_combined_importer.py` + `blagic_attos_importer.py`.
   `services/import_service.py::_try_combine_with_previous` (CASE 1B/2B
   Šumaprom) prosljeđuje `stats["incoterm_code"]`.
4. **Excel-only importeri bez PDF-a preskočeni** (nema slobodnog teksta za
   skeniranje): `sumaprom_excel_parser.py`, `imamoglu_excel_importer.py`,
   Medicopharm Excel grana.
5. **`importers/vendors/blagic/blagic_importer.py` NAMJERNO preskočen** —
   potvrđeno (grep + gitnexus) da je mrtav kod: jedini "živi" poziv je
   kroz `BlagicStrategy` (`importers/pdf/blagic_strategy.py`), koja NIJE
   registrovana u `strategy_registry.py`. Taj sloj (`PDFParseStrategy.
   extract() -> List[InvoiceLine]`) uz to nema ni mjesto za header-level
   metapodatak poput incoterm-a.
6. `gui/tabs/faktura_view.py::_apply_import_result_to_header()` — upisuje
   `draft.uslovi_kod = result.incoterm_code` samo ako je polje prazno
   (isti "ne prepisuj ručni unos" obrazac kao izvoznik/uvoznik/valuta).
7. `AGENTS.md` — nova MORA-konvencija (odmah poslije `consumed_paths`
   pravila): svaki importer koji ekstraktuje tekst fakture MORA pozvati
   `detect_incoterm()` — pokriva "buduće parsere" iz korisničkog zahtjeva
   dokumentacijom, ne centralnim kodom (isti stil kao postojeće
   konvencije u ovom fajlu).

GitNexus impact: `ImportResult` upstream **CRITICAL** (115 impacted, 73
direktno) — prijavljeno korisniku PRIJE izmjene po AGENTS.md protokolu
(project_rooms/2026-07-26_paritet-isporuke-auto-detekcija.md). Izmjena je
additive (1 novo opciono polje), ne dira postojeće pozive. Svi pojedinačni
importer entry-point-ovi provjereni kao LOW (spot-check: `import_kg_fashion`
4 impacted/LOW). Finalni `detect_changes(all)` nakon svih izmjena vratio
**"critical"** risk_level zbog OBIMA (21 affected_processes — svaki
dodirnut parser je step 1-3 u više execution flow-ova), NE zbog
neočekivanog uticaja: svi touched simboli su tačno oni koje sam namjerno
mijenjao (nijedan iznenađujući pogodak). Isti obrazac kao §66 "GitNexus
impact HIGH ≠ stvaran rizik" — topološka centralnost ne znači stvaran
rizik kad je diff additive i testovi prolaze.

Testovi: `tests/unit/test_incoterm_utils.py` (16 testova — sve formulacije
+ no-match + neispravan kod + case-insensitive), `tests/unit/
test_faktura_view_incoterm_header.py` (3 testa — popuni/ne-prepiši/prazno).
Svaki vendor testiran pojedinačno nakon izmjene (`pytest -k <vendor>`) —
0 regresija. Pun test suite: 1250 passed (+19 novih), 85 skipped, 5
xfailed, ista 2 pre-postojeća nepovezana problema
(`test_xml_parser_fix.py`, `test_model_benchmark.py`).

**Nema stvarnih PDF/tekstualnih fixtura faktura u repou** (`najavauvoza/`
folder ne postoji lokalno) — detekcija nije provjerena protiv stvarnog
teksta stvarne fakture, samo protiv sintetičkih string primjera u
testovima. Preporuka: korisnik potvrdi na sljedećem uvozu fakture koja
sadrži paritet u tekstu.

Svi importer fajlovi + `faktura_view.py` + `import_result.py` + `services/
import_service.py` sinhronizovani u `dist_client` mirror (4 fajla su imala
trivijalan pre-postojeći BOM/trailing-newline drift, nesemantički — potvrđeno
`diff --strip-trailing-cr` prije i poslije).

---

## 70. Agent V2 plan v2.1 — planer/workflow postaje obavezan scope, plan usklađen sa paralelnim radom (2026-07-26)

Korisnička odluka poslije v2.0: procjena vremena u danima je pogrešan model
jer plan realizuje **više paralelnih AI agenata**, ne jedan developer koji
kuca kod ručno — potvrđeno u praksi istog dana (Faza −1 i Faza 0 su završene
u paralelnoj sesiji dok je ovaj dokument još bio u izradi, commiti `2b4e815`,
`76c5a89`, `96a2911`). Tri eksplicitne odluke korisnika:

1. **Planer (Faza 7) i nivoi automatizacije (Faza 8) nisu uslovni, nego
   obavezan scope.** Korisnik želi tačno taj tok: jedna komanda pokreće cijeli
   proces do XML-a, agent vodi tok uz obavezne pauze na kapijama (Režim C iz
   Faze 8). Režimi A/B ostaju dizajnirani ali se ne izlažu kao prekidač dok se
   izričito ne zatraži.
2. **Konsolidacija alata 12 → 8** — potvrđena bez izmjene.
3. **Kill-switch `DEKLARANT_AGENT_V2` default `False`** — potvrđen bez izmjene,
   već implementiran u `config/settings.py` (Faza −1.C).

Procjena obima u `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` §25 je
preformulisana: brojke po fazi su **relativna implementaciona složenost**
(S/M/L), ne radni dani. Stvarno ograničenje wall-clock vremena nije brzina
pisanja koda (agenti pišu kod i pokreću testove u minutama), nego: (a)
kritični put — redoslijed faza koje moraju biti sekvencijalne (§25.2, deset
koraka), (b) obavezan korisnički pregled na HIGH/CRITICAL `gitnexus_impact`
nalazima (npr. `draft.revision` je dirao 278 pogođenih simbola), (c) korisnikov
dnevni token/poruka budžet — po njegovoj vlastitoj procjeni ovo je realno
najveće ograničenje.

**Faza 7 (planer) je jedina faza sa realno visokom implementacionom
složenošću** (§25.3) — ne zbog obima novog koda, nego zbog inverzije
zavisnosti u `_puna_auto_pipeline` (GUI pozivi `fw._on_*` i `QMessageBox` moraju
izaći iz servisnog sloja prije nego workflow orkestrator može voditi faze).

**Status Faze −1 i Faze 0** (za buduće agente koji čitaju plan): obje su
ZAVRŠENE prije nego što je v2.1 plan dovršen — vidi status-blokove direktno u
§10 i §11 plana. Fixture iz Faze 0 koristi polje `expected_sloj`, ne
`reachable_branch` kako je originalni primjer u planu predložio — isto
značenje, plan je ažuriran da to ne tretira kao neusklađenost.

---

### §71 — Bugfix: paritet isporuke (§70) se nije upisivao — unified import workflow ga nikad nije nosio (2026-07-26)

Korisnik uživo testirao §70 (auto-detekcija pariteta) — uvezao fakturu
`1476 BIH.pdf` (Medicopharm, tekst sadrži "PARITET: CIP BIJELJINA") i Rb.20
je ostao prazan. Provjereno direktno: `parse_medicopharm_pdf()` VRAĆA
ispravno `incoterm_code='CIP'` — parser i `detect_incoterm()` rade
besprijekorno. Bug je bio DALJE niz tok.

**Pravi uzrok**: `FakturaView` ima DVA paralelna toka za primjenu uvoza:
- **Legacy** (`_on_import_finished_legacy`) — poziva
  `_apply_import_result_to_header(result)` direktno na `ImportResult`
  (ovdje sam u §70 dodao `incoterm_code` i RADI).
- **Unified** (`_on_import_finished`, default put kad
  `_can_use_unified_manual_import()` vrati True — što je normalan slučaj)
  — ide kroz potpuno drugi lanac modela koji NIKAD nije nosio
  `incoterm_code`: `ImportResult` → (`adapters.from_import_result`)
  → `ImportCandidate` → (`prepare_service.prepare_import`) →
  `PreparedInvoice` → (`apply_service._apply_header_if_empty`) → `draft`.
  Ni jedan od ta 3 modela (`ImportCandidate`, `PreparedInvoice`) nije imao
  `incoterm_code` polje — §70 je popravio SAMO legacy put, koji se u
  praksi rijetko koristi.

Isti gap postoji i za Agent (chat) uvoz: `gui/tabs/agent/models/file_item.py`
`FileItem` model (ima eksplicitan komentar "⭐ Zaglavlje (iz ImportResult) -
za _apply_import_result_to_header" uz exporter/importer/currency) takođe
nije imao `incoterm_code`, niti ga je `ProcessingWorker.run()` prenosio sa
`ImportResult` na `FileItem`.

**Fix — dodano `incoterm_code` na SVA 4 mjesta u lancu**:
1. `services/import_workflow/models.py::ImportCandidate`
2. `services/import_workflow/adapters.py` — `from_import_result()` I
   `from_file_item()` (oba, isti gap na oba ulaza)
3. `services/import_workflow/plan_models.py::PreparedInvoice`
4. `services/import_workflow/prepare_service.py` — merge petlja (prvi
   neprazan pobjeđuje, isti obrazac kao currency/exporter)
5. `services/import_workflow/apply_service.py::_apply_header_if_empty` —
   upisuje `draft.uslovi_kod` samo ako prazan (isti obrazac)
6. `gui/tabs/agent/models/file_item.py::FileItem` — novo polje
7. `gui/tabs/agent/widgets/processing_worker.py::ProcessingWorker.run()` —
   prenosi `result.incoterm_code` na `file_item.incoterm_code`

GitNexus impact: `ImportCandidate` upstream MEDIUM (24 impacted, 8
direktno — potvrđuje da je ovo zajednički put i za ručni i za agent uvoz).
`detect_changes` poslije: "critical" po obimu (`ProcessingWorker.run()` je
step 1 u više execution flow-ova), ali svi touched simboli potvrđeni kao
namjerni (uklj. lažno pripisan `_apply_party_to_exporter` — samo pomjeren
3 linije, tijelo netaknuto).

**Verifikacija uživo**: ponovljen tačan scenario korisnika —
`parse_medicopharm_pdf()` → `from_import_result()` → `prepare_import()` →
`_apply_header_if_empty()` na stvarnom fajlu `1476 BIH.pdf` — `draft.
uslovi_kod` sad ispravno postaje `'CIP'` na svakom koraku lanca.

**Pouka za buduće auto-popune zaglavlja**: ako se doda novo polje koje
treba teći iz parsera do drafta, MORA se provjeriti OBA toka
(`_apply_import_result_to_header` ZA legacy, ali i cijeli
`ImportCandidate`→`PreparedInvoice`→`_apply_header_if_empty` lanac za
unified/agent put) — jednog nije dovoljno, jer je unified put danas
DEFAULT za ručni uvoz.

Testovi: `test_import_workflow_adapters.py` (+2 — `test_cuva_incoterm_code`
na oba adaptera), `test_import_workflow_prepare.py` (+2 — nova
`TestPrepareIncoterm` klasa), `test_import_workflow_apply.py` (regresioni
assert na postojećem end-to-end testu, sa komentarom da referiše ovaj bug).
Pun test suite: 1287 passed (+37 od početka §70 rada), 85 skipped, 5
xfailed. 2 NOVA nepovezana fail-a (`test_ima_tacno_12_alata`,
`test_svi_ocekivani_alati_postoje`) — potiču iz TUĐEG commit-a `d8de0a3`
("Faza 1 — konsolidacija alata 12→9") koji je sletio usred ove sesije,
nepovezano, nedirano.

**Napomena o grani**: ovaj commit je prvo greškom sletio na
`feature/agent-v2` (neočekivan `git checkout` od strane drugog agenta u
istom working tree-u, usred moje sesije) — cherry-pick-ovan nazad na
`windows` bez diranja `feature/agent-v2`.

---

### §72 — Uvećan font: kontekstni meni, dijalog izmjene tarife, tabela auto-primijenjenih tarifa (2026-07-26)

Korisnička primjedba (uz screenshot): font u dijalogu "Promijeni tarifni
broj" (otvara se desnim klikom na tabelu → izmjena tarife za više
odabranih stavki) i u tabeli dijaloga "Automatski ažurirane tarife" (§67)
je previše sitan i nečitljiv; isto i kontekstni meni (desni klik) za izbor
akcije.

**Uzrok**: `QMenu` (kontekstni meni, `_on_table_context_menu`) i
`QInputDialog.getText()` (`_on_bulk_change_tariff`) nisu imali nikakav
eksplicitan stylesheet — nasljeđivali su globalni app font (Segoe UI 9pt
na Windows-u, `run.py`), što je za ove specifične dijaloge (rijetko
korišćeni, gusti tekst) ispalo premalo. Tabela u `_build_tariff_table_widget`
(dijeli je `_show_tariff_preview_dialog` i `_show_tariff_table_info_dialog`,
§67/§70) je imala `font-size: 13px` — deklarisano, ali i dalje ocijenjeno
premalim od strane korisnika.

**Fix**:
- `QMenu` u `_on_table_context_menu` — `font-size: 15px`, veći padding po
  stavci menija (8px 24px) za lakše ciljanje mišem.
- `_on_bulk_change_tariff` — zamijenjen `QInputDialog.getText()` (statička
  metoda, ne dozvoljava stylesheet) ručnom `QInputDialog` instancom
  (`.setLabelText()`/`.setTextValue()`/`.exec()`) sa `font-size: 15px`
  (label/lineedit) i `14px` (dugmad) — identično ponašanje, samo čitljivije.
- `_build_tariff_table_widget` — `font-size` stavki 13px→16px, header
  13px→15px (eksplicitno, jer `QHeaderView::section` ne nasljeđuje
  font-size od `QTableWidget` u Qt QSS kaskadi), padding povećan.
- Intro `QLabel` tekst i OK/Potvrdi/Odustani dugmad u
  `_show_tariff_preview_dialog` i `_show_tariff_table_info_dialog` —
  eksplicitan `font-size: 15px`/`14px` (prije nedeklarisano, nasljeđivalo
  globalni 9pt).

GitNexus impact: `_on_table_context_menu` LOW (0 impacted, izolovan
signal handler), `_build_tariff_table_widget` LOW (5 impacted, dijele je
samo 2 poznata dijaloga). `detect_changes` poslije: LOW, 0
affected_processes, svi touched simboli namjerni (uklj. lažno pripisanu
`_show_scrollable_info_dialog` — samo pomjerena linija, tijelo netaknuto).

Testovi: postojeći `test_faktura_view_auto_applied_notice.py` i dalje
prolazi (ne testira render/pixel, samo strukturu podataka — vizuelna
promjena bez novog testa, po istom principu kao §69 boja dugmadi). Pun
test suite: 1262 passed, ista 2 pre-postojeća nepovezana problema.

Nije dodat automatski test za font-size (isto obrazloženje kao ranije
vizuelne izmjene — Qt offscreen test ne provjerava stvaran render).
Potrebna korisnička vizuelna potvrda uživo.

---

## 71. Agent V2 (feature/agent-v2) — kritični wiring gapovi popravljeni (2026-07-27)

Nakon što je cio plan (Faze -1 do 10) implementiran na `feature/agent-v2`,
detaljan pregled (čitanje diff-a, praćenje stvarnih poziva, ne samo
postojanja fajlova) otkrio je da su servisi za svaku fazu izgrađeni i
testirani IZOLOVANO, ali gotovo nijedan nije bio povezan na stvarni
ulazni tok (`_handle_message`, `_execute_tool`, `_izvezi_xml`,
`_puna_auto_pipeline`). Detaljan izvještaj:
`agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md`.

**Najozbiljniji nalaz — nije bio dio originalnog pregleda, otkriven tek pri
pisanju testova**: `_audit_routing("switch", agent_v2=agent_v2, ...)` i
`_audit_routing("v2_resolver", action=..., target=..., confidence=...)`
prosljeđuju kwargs koje `AuditEvent` dataclass ne prihvata — `TypeError` na
SVAKI poziv `_handle_message`, bez obzira na sadržaj poruke ili kill-switch
vrijednost. Cio agent chat je bio potpuno nefunkcionalan na ovoj grani.
Nijedan od preko 1200 postojećih testova ovo nije uhvatio jer nijedan ne
poziva `_handle_message` direktno (svi testiraju `_handle_message_v2` ili
interne funkcije, zaobilazeći ovu liniju). **Pouka**: testovi koji mockuju
sve zavisnosti mogu propustiti bug u samom ulazu funkcije — vrijedi imati
barem jedan test koji zove pravi top-level entry point sa minimalnim
mockovanjem.

**Drugi nalaz**: `_xml_preflight()` je uvozio `export_to_xml` ali ga NIKAD
nije pozivao — samo provjeravao da `items` nije prazan. Prava greška u
XML builderu bi bila prijavljena kao READY. Popravljeno pozivanjem
`AsycudaXMLBuilder(...).build()` nad JSON round-trip kopijom drafta (ne
originalom — `_apply_known_tariff_corrections()` unutar `build()` mutira
`draft.items` u hodu, pa se preflight ne smije raditi nad produkcionim
draftom direktno).

**Otkriven i pre-postojeći bug u `scripts/sync_dist_client.py`**:
`normalize()` nije normalizovao CRLF/LF stil, samo BOM i trailing
whitespace — svaki fajl gdje root koristi LF a dist_client CRLF je bio
lažno prijavljen kao "stvarna razlika". Popravljeno.

**Namjerna scope odluka pri `dist_client` sinhronizaciji**: `--apply` je
prvi put pokrenut bez ograničenja i otkrio da dist_client kasni za root-om
za **preko 330 fajlova** (nepovezanih sa Agent V2 — akumulirano tokom
istorije projekta). Taj širi drift je NAMJERNO ostavljen netaknut (vraćen
`git checkout --` na prethodno stanje) — sinhronizovano je samo 7 fajlova
stvarno vezanih za ovu popravku. Širi resync ostaje otvorena odluka za
korisnika, van scope-a ovog zadatka.

**Arhitektonska odluka o Fazi 7**: orkestrator (`declaration_workflow_service.py`)
NE radi punu inverziju zavisnosti `_puna_auto_pipeline` (uklanjanje
`QMessageBox`/`processEvents()`) — to ostaje veliki, rizičan zahvat. Umjesto
toga, `_puna_auto_pipeline` se ponovo koristi kao provjerena "prva polovina",
a orkestrator dodaje nedostajuću "drugu polovinu" (zaglavlje → cross-tab →
xml preflight → izvoz).

---

## 72. Sigurnosni audit — DB runtime nalog je superuser (2026-07-27)

Read-only provjera aktivnog servera `192.168.100.154` potvrdila je PostgreSQL
16, TLS sesiju i `scram-sha-256`, ali i da aplikacijski DB nalog ima
`rolsuper=true`. To je kritičan rizik u kombinaciji sa parser plugin sistemom
koji izvršava izabrani `.py` kroz `exec_module()`: kompromitovan parser ili
`.env` može ugroziti cijeli DB server, ne samo aplikacijske tabele.

Prioritet prije šire Agent V2 automatizacije: poseban least-privilege runtime
nalog, rotacija postojeće 8-znakovne lozinke i prelazak sa `sslmode=prefer`
na najmanje `require`, zatim `verify-full`. Detalji i kriteriji zatvaranja:
`docs/SECURITY_AUDIT_2026-07-27.md`.

---

## 73. Sigurnosni hardening nakon audita (2026-07-27)

Sigurnosni P0/P1 kod je realizovan na `feature/agent-v2` i preslikan u
odgovarajuće `dist_client` module. Kanonske odluke za buduće izmjene:

1. **DB runtime mora biti least-privilege i stvarno TLS.** Aplikacija koristi
   `deklarant_app`; konekcioni pool na startupu provjerava `pg_stat_ssl` i
   `pg_roles` i odbija netls sesiju ili ulogu sa `SUPERUSER`, `CREATEDB`,
   `CREATEROLE`, `REPLICATION` ili `BYPASSRLS`. Podrazumijevani minimum je
   `sslmode=require`; cilj infrastrukture ostaje `verify-full`.
2. **Eksterni parser je default-deny.** Dozvoljen je samo uz eksplicitno
   `ALLOW_EXTERNAL_PARSER_PLUGINS=true`, konfigurisan javni ključ i važeći
   RSA-PSS/SHA-256 `.py.sig`. Validacija mora ostati statička AST provjera;
   nikad ne importovati modul prije provjere potpisa.
3. **Obavezna readiness provjera je fail-closed.** Exception ili nedostupan
   XML builder proizvodi blokirajući `REQUIRED_CHECK_FAILED`; tehnički kvar se
   ne smije tretirati kao preskočena neobavezna provjera.
4. **Readiness rezultat pripada tačnoj `draft.revision`.** Revizija se ponovo
   provjerava poslije korisničke potvrde i izbora fajla; svaka međuvremena
   izmjena zahtijeva novu provjeru.
5. **XML ulaz ide isključivo kroz `services/security/safe_xml.py`.** Direktni
   `ElementTree.parse`/`lxml.parse` za poslovne fajlove nisu dozvoljeni.
6. **LLM ne proizvodi carinski zaključak bez lokalnog kandidata/dokaza.** Svi
   provider pozivi idu kroz `LLMProvider`; direktan `Groq(...)` iz poslovnog
   servisa je zabranjen.
7. **Log handleri moraju imati `SensitiveDataFilter`.** Tajne, DB URL,
   prepoznati API ključevi, JIB i korisničke Windows putanje rediguju se prije
   izlaza.

Operativno još otvoreno: aplikacija više ne koristi istorijski nalog
`radovan`, ali PostgreSQL administrator mora invalidirati njegov stari login/
lozinku; produkcijski server zatim treba vlastiti CA za `verify-full`, a
finalni EXE i installer Authenticode potpis i smoke test.

---

## 74. AdminView sidebar nevidljiv tekst u frozen buildu — Path(__file__) vs BUNDLE_ROOT (2026-07-27)

Prvo stvarno korisničko testiranje izgrađenog EXE-a (build_windows.bat) je
otkrilo da je tekst u Admin sidebar-u (Upravljanje Parserima, Baza Podataka,
Analitika, Logovi, Sistemske Informacije, Licenca, Učenje iz XML-ova) skoro
nevidljiv — svijetlo siva boja na bijeloj pozadini, dok je ostatak Admin
panela (npr. Plugin Management sadržaj) izgledao normalno.

**Uzrok**: `gui/tabs/admin/admin_view.py::_apply_styles()` je računao
putanju do `admin_tab.qss` preko `Path(__file__).parent.parent.parent /
"styles"`. U dev modu `__file__` je stvaran fajl na disku i traversal
radi. U **frozen (PyInstaller) buildu** `__file__` za bundlovan modul ne
vodi do stvarnog `styles/` foldera (koji fizički živi u
`dist/DeklarantPro/_internal/styles/`, ne pored .exe-a) — `stylesheet_path.exists()`
je tiho vraćao `False`, `setStyleSheet()` se nikad nije pozvao, i sidebar
tekst je pao na naslijeđenu (netačnu) boju iz globalnog stylesheet-a.

**Ispravan obrazac (već postoji u projektu, samo nije korišten ovdje)**:
`config/settings.py::PathSettings.styles_dir` = `BUNDLE_ROOT / "styles"`,
gdje je `BUNDLE_ROOT = Path(sys._MEIPASS)` kad je frozen, inače project
root. `gui/main_window.py` ovo već ispravno koristi
(`get_path_settings().styles_dir`) za glavni stylesheet — `admin_view.py`
je jedini QSS-fajl-loader u projektu koji je to zaobišao i ručno računao
`__file__`-relativnu putanju.

**Provjereno**: nijedan drugi Admin panel (`plugin_panel.py`,
`system_panel.py`, `database_panel.py`, `settings_panel.py`,
`analytics_panel.py`) ne koristi `__file__`-relativno računanje — svi
imaju inline `setStyleSheet("""...""")`, pa nisu pogođeni istim bugom.

**Pouka za buduće GUI fajlove koji učitavaju vlastiti `.qss` fajl**:
uvijek koristiti `from config.settings import get_path_settings; ... =
get_path_settings().styles_dir / "ime.qss"` — nikad `Path(__file__).parent...`
za resurse koji moraju raditi i u frozen buildu. Ovaj bug se NE vidi u
dev modu (`python run.py`) — vidi se samo u stvarnom PyInstaller EXE-u,
što je razlog zašto je prošao nezapaženo do prve stvarne probe builda.

Fix: `gui/tabs/admin/admin_view.py::_apply_styles()`.

---

## 75. "Puna automatizacija" povezana na declaration_workflow_service orkestrator do XML izvoza (2026-07-27)

Korisnička primjedba nakon stvarnog testiranja izgrađenog EXE-a: "Puna
automatizacija" (Režim obrade kartica u Agent tabu) je izgledala praktično
identično kao "Uvezi u deklaraciju" jer stane odmah nakon kreiranja
naimenovanja — zaglavlje, cross-tab provjera, XML readiness i sam izvoz su
ostajali identično ručni u oba moda.

**Uzrok**: `AgentController._on_all_completed()` je za "Puna automatizacija"
pozivala `self._puna_auto_pipeline(fw, chat, all_processed_lines)` direktno
([agent_controller.py:665-673](gui/tabs/agent/agent_controller.py)) — ta
funkcija radi samo mase → tarife → validacija → naimenovanja, pa se
zaustavlja. Ovo je isti `_puna_auto_pipeline` koji je bio predmet ranije
popravke wiring gapova (§71) — sad je i sam njegov POZIVALAC promijenjen.

**Popravka**: ta grana sad poziva
`services.agent.workflow.declaration_workflow_service.run_declaration_workflow(self, chat, fw=fw)`
umjesto direktnog `_puna_auto_pipeline`. Orkestrator iznutra PONOVO KORISTI
`_puna_auto_pipeline` za prvu polovinu (mase/tarife/validacija/naimenovanja
— ništa se ne duplira), a zatim NASTAVLJA kroz preostale kapije (zaglavlje →
cross-tab → XML preflight → potvrda → izvoz). "Uvezi u deklaraciju" grana
nije dirana — i dalje radi samo uvoz, bez ikakve automatizacije, kako je i
namijenjeno.

Testovi ažurirani u `tests/unit/test_agent_controller_provjeri_nakon_uvoza.py`
— stari test je asertovao `ctrl._puna_auto_pipeline.assert_called_once()`
(sad netačno), zamijenjen provjerom da se `run_declaration_workflow` poziva
sa ispravnim `fw` argumentom. Patch cilja izvorni modul
(`services.agent.workflow.declaration_workflow_service.run_declaration_workflow`),
ne `agent_controller` modul — import unutar metode je odgođen (deferred),
pa patch na pogrešnom mjestu tiho ne bi ništa presreo.

Napomena: naimenovanja i dalje zahtijevaju eksplicitnu potvrdu deklaranta
(QMessageBox sa default "Ne") prije nego pipeline nastavi — ovo NIJE
promijenjeno, i ne treba biti (compliance kapija za porijeklo/EUR.1/PE,
vidi §4 ovog dokumenta). Korisnik mora obratiti pažnju na taj dijalog.

---

## 76. "Puna automatizacija" — fokus se vraćao na Faktura tab usred workflowa, skrivajući nastavak (2026-07-27)

Nakon §75 (orkestrator povezan do XML izvoza), korisnik je uživo testirao
rebuild i prijavio da izgleda "potpuno isto kao ranije" — nakon potvrde
povlastice otvara Faktura tab i tu je kraj.

**Uzrok**: `puna_auto_pipeline` (koju `run_declaration_workflow` iznutra
poziva za prvu polovinu — mase/tarife/validacija/naimenovanja) na SVOM
VLASTITOM kraju poziva `_otvori_faktura_tab_nakon_uvoza()`
(`import_pipeline_service.py:700`), koja eksplicitno prebacuje glavni
`QTabWidget` na Faktura tab. Ovo je bilo namjerno za stari, plitki tok
(gdje je Faktura tab bio STVARNI kraj procesa). Ali `run_declaration_workflow`
NASTAVLJA nakon toga (zaglavlje → cross-tab → xml preflight → izvoz) — te
poruke se ispravno generišu u Agent chatu, ali korisnik ih nikad nije vidio
jer je fokus ostao na Faktura tabu.

**Fix**: `AgentController._on_all_completed()`, grana "Puna automatizacija",
nakon `run_declaration_workflow(...)` poziva eksplicitno vraća fokus na
Agent tab (`self.view.parent()`, isti `parent`/`QTabWidget` koji je već
pronađen ranije u metodi za Faktura-tab-switch). Novi test
(`test_agent_puna_automatizacija_vraca_fokus_na_agent_tab_nakon_workflowa`)
provjerava redoslijed: `setCurrentWidget` prvo poziva Faktura tab (iz
`puna_auto_pipeline`), pa Agent tab (fix) kao POSLJEDNJI poziv.

**Pouka**: kad se servis koji sam po sebi mijenja UI fokus (tab switch,
dijalog) PONOVO UPOTREBLJAVA kao "prva polovina" većeg orkestriranog toka,
provjeriti da li taj servisov own-completion side-effect (npr. tab switch)
skriva nastavak orkestracije — ne samo da li se logika izvršava, nego i
da li je REZULTAT te logike vidljiv korisniku.

---

## 77. "Puna automatizacija" — naimenovanja se kreirala prije nego istorijska tarifna provjera stvarno završi (2026-07-27)

Nakon §76 (fokus vraćen na Agent tab), korisnik je uživo testirao i vidio
stvaran ishod workflowa: `items_validated` kapija je blokirala sa "naimenovanje
1: Naziv robe je obavezan, Tarifni broj je obavezan, Nedostaje zemlja
porijekla" — iako je Faktura tab jasno prikazivao popunjene podatke za svih
94 stavki. Korisnik je precizno dijagnostikovao: "Nije završen proces u tabu
faktura, tek kad se tu sve završi proces može ići dalje."

**Uzrok**: `_on_validate_all(auto=True)` (faza 3 u `_puna_auto_pipeline`)
iznutra poziva `_run_historical_tariff_validation(auto=True)`
(`faktura_view.py:4650`), koja pokreće `HistoricalValidationWorker` kao
**fire-and-forget QThread** (`worker.start()`) i odmah se vraća — stvarni
rezultati (auto-primijenjeni tarifni brojevi iz historijskog učenja) stižu
tek KASNIJE preko `finished_validation` signala i slota
`_on_historical_validation_finished` (dokumentovano u samom docstringu:
"DB upiti po stavci su prespori za UI thread", §59). `_puna_auto_pipeline`
NIJE čekala ovaj worker — nastavljala je odmah na fazu 4 (EUR.1/PE potvrda)
i fazu 5 (kreiranje naimenovanja) dok je worker možda još radio.

**Napomena za buduće debugiranje**: pregledom koda, ovaj konkretan worker
mijenja samo `tarifni_broj` (ne `naziv_robe`/`zemlja_porijekla`), pa ne
objašnjava nužno SVE prijavljene prazne fields — mehanizam (async gap bez
čekanja) je potvrđen i popravljen, ali ako se prazna naimenovanja i dalje
pojave nakon ove popravke, treba tražiti DRUGI izvor kašnjenja (npr. neki
drugi QThread worker u `_on_calculate_masses`/`_on_auto_fill` lancu).

**Fix**: nova `_wait_for_historical_validation(fw, timeout_ms=30000)` u
`import_pipeline_service.py` pumpa Qt event loop (`QEventLoop` + `QTimer`
sigurnosni timeout) dok `fw.historical_validation_worker` stvarno ne završi,
pozvana odmah nakon faze 3, prije faze 4. Provjera
`isinstance(worker, QThread)` (ne samo `is not None`) je NAMJERNA — bez nje
bi `MagicMock()` u testovima (`isRunning()` na MagicMock-u je uvijek truthy)
izazvao pravi hang do timeout-a u SVAKOM postojećem testu `_puna_auto_pipeline`
(otkriveno prvim pokušajem — puna svita je "visjela" dok nije dodana ova
provjera).

**Pouka**: kad se u orkestrator (`_puna_auto_pipeline`) ponovo koriste
postojeće GUI metode (`_on_validate_all`, `_on_create_naimenovanja`) sa
`auto=True`, provjeriti da li te metode INTERNO pokreću bilo koji
fire-and-forget QThread — "auto" parametar obično samo preskače DIJALOGE,
ne garantuje sinhronost. Isti obrazac vrijedi provjeriti za bilo koji budući
dodatak u pipeline lancu.

Testovi: 3 nova u `test_puna_auto_pipeline.py` (`TestCekanjeNaIstorijskuValidaciju`)
— stvaran QThread se čeka, `None`/`MagicMock` worker se preskače bez čekanja.
Puna svita: 1415 passed, 0 failed (isti 3 pre-postojeća nepovezana pada).

Usput ispravljen i nepovezan propust: **`deklarant_sistem.db` (sadrži
`tarifa_2026`, 13556 redova) nikad nije bila kopirana pored .exe pri ručnom
build+test ciklusu ove sesije** — potvrđen već dokumentovan obrazac (§44/45):
baza je namjerno READ-WRITE/lokalna i NE bundluje se u `_internal/` preko
`spec.datas` (samo `zvanicna_tarifa.db`/`inspection_rules.db` su read-only
referentni podaci), nego živi POKRAJ `.exe`-a i mora se ručno kopirati
nakon svakog builda (isto kao `.env`) — nije bila potrebna izmjena spec fajla
niti `_resolve_db_path()`, samo propušten ručni korak u test okruženju.

---

## 78. "Puna automatizacija" — STVARAN uzrok praznih naimenovanja: items_created kapija prihvatala zastarjela naimenovanja iz vraćene sesije (2026-07-28)

Nakon §77 (async čekanje na istorijsku validaciju — real fix, ali nije riješio
glavni simptom), duga uživo istraga (dvije sesije, korisnik testirao i ručni
i automatski put više puta) je konačno pronašla PRAVI uzrok.

**Ćorsokaci prije pravog nalaza** (za buduće agente — ne ponavljati):
1. Pretpostavka da `deklarant_sistem.db` treba u `spec.datas` — netačno,
   već dokumentovano u §44/45 da je namjerno read-write/lokalna, živi pored
   `.exe`-a. Samo je propušten ručni korak kopiranja u test okruženju.
2. Pretpostavka o async gap-u u istorijskoj validaciji (§77) — REALAN i
   popravljen problem, ali NIJE bio uzrok ovog konkretnog simptoma.
3. **Korisnik je jedan test slučajno pokrenuo na potpuno DRUGOM, zastarjelom
   EXE-u** (`.worktrees/agent-v2/dist/DeklarantPro/`, izgrađen 12:31 istog
   dana, prije svih popravki) umjesto na ispravnom
   (`deklarant_pro/dist/DeklarantPro/`) — otkriveno tek preko
   `Get-Process DeklarantPro | Select Path`. **Pouka: UVIJEK provjeriti
   putanju pokrenutog procesa prije analize test rezultata kad postoji više
   worktree-ova sa vlastitim `dist/` folderima.**

**Ključan dijagnostički korak**: Agent chat panel ima 3 taba (Agent /
Aktivnosti / Pitanja) — `chat.add_agent_message()` ide na "Agent" tab,
`chat.add_activity()` ide na "Aktivnosti" tab. Korisnik je dosad gledao samo
"Agent" tab; tek uvid u "Aktivnosti" je pokazao da se tok zaustavlja na
`"🔄 Faza: Završeno"` odmah nakon uvoznog EUR1 dijaloga — **nijedna** poruka
iz `_puna_auto_pipeline` (izračun masa, auto-popuna, validacija) se nikad
nije pojavila, dokazujući da ta funkcija NIKAD nije pozvana.

**Pravi uzrok**: `items_created` kapija (`declaration_workflow_state.py`) je
provjeravala samo `bool(draft.items)`. Aktivnosti log je otkrio liniju
"⚠️ Prethodna sesija prekinuta u fazi: analyzing" (Blagić fakture) — session
restore mehanizam je vratio draft koji je već imao BAREM JEDNO zastarjelo
naimenovanje iz DRUGE, ranije/prekinute sesije, nepovezano sa trenutnim
94 stavki (Medicopharm 1476/26). `bool(items)` je zato lažno prošao,
`run_declaration_workflow._run()` NIKAD nije pozvala
`ImportPipelineService.puna_auto_pipeline()` (koja bi inače, preko
`create_smart_group()`, prvo obrisala stara items i kreirala prava), a
`items_validated` kapija je onda ispravno prijavila da to STARO,
nepovezano naimenovanje nema popunjena polja — što JE bilo tačno, samo za
pogrešno naimenovanje.

**Dokaz da logika grupiranja nikad nije bila problem**: dijagnostički
`logger.warning` (privremeno ugrađen, sad uklonjen) je pokazao da ručni
klik "Provjeri"→"Kreiraj Naimenovanja" na ISTIM 94 stavki daje **26 potpuno
ispravno popunjenih naimenovanja** — potvrđujući da je `create_smart_group()`
uvijek radila ispravno; automatski put je jednostavno nikad nije pozivao.

**Fix**: `items_created` kapija sad provjerava da SVAKA `invoice_lines`
stavka ima `assigned_naimenovanje_id` koji pokazuje na POSTOJEĆI `item_id`
u `draft.items` — ne samo da lista nije prazna. Test fixture
`_minimal_ready_draft()` (`test_agent_v2_wiring_fixes.py`) ažuriran da
postavi tu vezu (odražava stvarno stanje nakon `create_smart_group()`).
Novi test `test_zastarjelo_naimenovanje_iz_prethodne_sesije_ne_prolazi_items_created`
direktno dokazuje popravku.

**Pouka za buduće kapije**: kad kapija provjerava "da li X postoji" kao
zamjenu za "da li je X ISPRAVNO/AŽURNO kreiran za TRENUTNI kontekst", uzeti
u obzir perzistentno/vraćeno stanje (session restore, cache, stale
reference) — `bool(nešto)` nije isto što i "nešto je validno OVDJE i SADA".

Puna svita: 1416 passed, 0 failed (isti 3 pre-postojeća nepovezana pada).

---

## 79. "Puna automatizacija" — izračun masa lažno tretiran kao pad kad je već sve popunjeno (2026-07-28)

Neposredno nakon §78 (items_created popravka), korisnik je uživo testirao i
potvrdio da `_puna_auto_pipeline` **konačno biva pozvana** ("🤖 Pokrećem
pripremu fakture i naimenovanja..." se prvi put pojavljuje u "Aktivnosti"
tabu) — ali odmah pada na prvoj fazi: "❌ Izračun masa nije uspio", iako je
Faktura tabela jasno prikazivala ispravno popunjene bruto/neto vrijednosti
po stavci (npr. 5.58/5.13 kg za prvu stavku).

**Uzrok**: `_on_calculate_masses(auto=True)` (`faktura_view.py:4984`) vraća
`False` u DVA različita slučaja koja se ne razlikuju na povratnoj
vrijednosti:
1. stvaran neuspjeh (nedostaju/neispravne vrijednosti, `mass_mismatches`)
2. **benigno stanje** — `updated_count == 0` jer SVE stavke već imaju obje
   težine (`faktura_view.py:5180`, "Nema stavki za update - sve imaju obe
   težine") — u interaktivnom modu ovo prikazuje informativnu poruku ("Sve
   težine već imaju upisane obe težine... Nema šta da se računa"), ali
   povratna vrijednost je i dalje `False`.

`_puna_auto_pipeline` je oba slučaja tretirala identično kao fatalan pad
("mase" faza → `FAILED`, `can_continue=False`), iako je slučaj 2 potpuno
očekivan kad parser (npr. za Medicopharm PDF) direktno ekstraktuje
bruto/neto po stavci, bez potrebe za toolbar-total redistribucijom.

**Fix**: dodata provjera prije poziva (`bez_mase = sum(1 for l in
invoice_lines if not l.bruto_kg or not l.neto_kg)`) — isti obrazac kao već
postojeća provjera "bez_tarife" za auto-popunu tarifa (faza 2). Ako sve
linije već imaju obje težine, faza mase se PRESKAČE (uz poruku "✅ [Auto]
Sve stavke već imaju izračunatu masu — preskačem") umjesto da poziva
`_on_calculate_masses`, koja bi vratila `False` i lažno zaustavila cijelu
automatizaciju.

**Namjerno NIJE dirano**: `_on_calculate_masses` sama — mijenjanje njene
povratne vrijednosti (npr. razlikovanje "nema šta"/"pravi pad") bi
zahtijevalo provjeru SVIH pozivalaca (uklj. GUI dugme), veći i rizičniji
zahvat od potrebnog. Ciljani fix ostaje samo u `_puna_auto_pipeline`
(orkestrator), ne u dijeljenoj View metodi.

Testovi: 2 nova u `test_puna_auto_pipeline.py`
(`TestPreskociMaseAkoVecPopunjene`) — dokazuju oba smjera (preskače kad je
sve popunjeno, i dalje poziva kad bar jedna stavka nema masu). Test helper
`_line()` ažuriran da eksplicitno postavi `bruto_kg=0, neto_kg=0` po
defaultu (MagicMock auto-atribut je uvijek truthy, što bi lažno "preskočilo"
fazu i u POSTOJEĆIM testovima bez ove eksplicitne postavke).

Puna svita: 1418 passed, 0 failed (isti 3 pre-postojeća nepovezana pada).

---

## 80. "Puna automatizacija" — auto-popuna Izvoznik/Primalac/Deklarant iz istorijskog XML-a (2026-07-28)

Nakon §75-79 (Puna automatizacija konačno radi kroz sve faze i zaustavlja se
tačno na Zaglavlju), korisnik je pokazao da dugme "Uvezi XML" u Zaglavlju
potpuno popuni Izvoznik/Primalac/Deklarant kolonu (pune adrese, JIB-ovi,
Tip deklaracije, kurs...), dok automatizacija ostavlja kolonu skoro praznu
(samo `izvoznik_naziv` iz uvoza fakture, Primalac/Deklarant potpuno prazni).
Zadatak: povezati isti mehanizam u automatizaciju.

**Istraženi mehanizam** (dva postojeća, ranije nepovezana puta do istog cilja):
- `services/agent/learning/exporter_xml_indexer.py::find_xml_for_pair()` —
  traži PAR (exporter [+ consignee_jib/naziv]) → putanja do najnovijeg
  istorijskog XML-a, iz `catalogs.exporter_xml_index` (prioritet: JIB > naziv
  primaoca > bilo koji primalac za tog izvoznika > fuzzy).
- `services/zaglavlje_service.py::ZaglavljeService.load_from_xml()` — puni
  ASYCUDA XML parser (isti kod koji koristi dugme "Uvezi XML" preko
  `zaglavlje_controller._on_import_xml`), vraća SVA header polja
  (adrese, JIB, kurs, incoterm, carinarnice...), za razliku od
  `faktura_view.py::_extract_header_from_xml()` (dugme "Prethodna
  deklaracija" u Fakturi) koji parsira samo uzak podskup polja.

**Zašto ne pozvati `_on_import_xml` direktno**: ta metoda poziva
`view.show_success/show_warning` koji otvaraju MODALNI `QMessageBox` (vidi
`base_view.py`) — blokirao bi headless automatizaciju čekajući klik.
Umjesto toga novi `services/agent/workflow/header_autofill_service.py::
auto_fill_header_from_history(ctrl, chat)` radi isti posao bez GUI dijaloga:
nađe XML preko `find_xml_for_pair`, parsira preko `ZaglavljeService.
load_from_xml`, i upisuje SAMO prazna polja direktno na `draft` (isti
obrazac kao `faktura_view.py::_apply_import_result_to_header` — "popunjava
samo prazna polja, ne prepisuje ono što je korisnik već unio"). Ako je
Zaglavlje tab trenutno otvoren, poziva `zaglavlje_tab.load_from_draft(draft)`
da osvježi prikaz (isti poziv kao `_on_load_previous_declaration`).

**Gdje je povezano**: `declaration_workflow_service.py::_run()`, tačno
prije `header_ready` kapije — ako kapija ne prolazi, prvo se pokuša
auto-popuna, pa se stanje ponovo izračuna; tek ako i dalje ne prolazi
(nema istorijskog XML-a za tog izvoznika, ili historijski XML ne pokriva
obavezna polja), kapija se zaustavlja normalno sa porukom za ručni unos —
to ostaje ispravno ponašanje kad automatizacija stvarno nema odakle da
povuče podatke.

**Namjerno NIJE dirano**: `_on_import_xml` (GUI dugme ostaje nepromijenjeno,
i dalje traži fajl ručno i prikazuje dijaloge), `_on_load_previous_declaration`
u Fakturi (odvojen, uži mehanizam — nije zamijenjen, samo mu je servisni
"punjeniji" parser sad dostupan i automatizaciji).

Testovi: novi `tests/unit/test_header_autofill_service.py` (6 testova) —
bez izvoznika, nema pogotka u indeksu, izuzetak iz baze, popuni samo prazna
polja (ne prepisuje postojeće), nema šta novo za popuniti → False, osvježi
otvoren Zaglavlje tab.

Puna svita: 1424 passed (1418 + 6 novih), isti 3 pre-postojeća nepovezana
pada (tool registry drift, hardkodovana Linux putanja u test_xml_parser_fix,
model_benchmark network error) + 1 pre-postojeći error — svi nepovezani sa
ovom izmjenom.

---

## 81. Naimenovanja Controller — brisanje ne smije pozvati save poslije delete (2026-07-28)

Kod brisanja aktivnog naimenovanja forma još prikazuje obrisanu stavku. Ako se
nakon `del items[index]` pozove navigacija koja prvo snima formu, podaci
obrisane stavke prepišu sljedeću stavku koja je zauzela isti indeks. Ispravan
redoslijed je: potvrda u View-u → Controller briše i renumeriše → postavlja
validan indeks → renderuje, bez save-before-navigation poziva. Numerička polja
forme moraju ostati `int`/`float`, a tarifni broj se normalizuje na cifre prije
upisa u draft; Controller dobija aktivni draft isključivo kroz getter.

---

## 82. Naimenovanja faze 5–8 — kontrolisano učenje i PE/XML pravila (2026-07-28)

Promjena tarife kroz Naimenovanja tab prolazi View signal → Controller →
NaimenovanjaService. Kod grupisanog naimenovanja povezane faktura-stavke uvijek
se nalaze preko `assigned_naimenovanje_ordinal`; obrazac `ordinal_no - 1` nije
ispravan. Baza znanja se ažurira tek poslije eksplicitne potvrde korisnika i za
svaku povezanu faktura-stavku zasebno.

Prihvaćeni tarifni prijedlog smije automatski promijeniti samo tarifni broj.
Zemlja porijekla i povlastica iz prijedloga nisu dovoljan dokaz i ostaju
nepromijenjene. PE1/PE2/PE3 se normalizuju i čuvaju u `attached_document4`
samo kada naimenovanje ima povlasticu; sekundarna PE polja se čiste, a zaglavlje
se svaki put ponovo gradi bez duplikata.

ASYCUDA XML import mutira postojeći draft objekat, čuva aktuelna transportna
polja, prazni reference svih globalnih dokumenata osim `DIS`, zatim osvježava
Naimenovanja i Zaglavlje kroz wrapper callback. View samo bira fajl, traži
potvrdu i emituje namjeru; ne smije nakon toga drugi put samostalno uvoziti XML.

---

## 83. Rub.31 trgovački naziv — GUI format ostaje ograničen na 280 znakova (2026-07-28)

Windows grana je autoritativna za formatiranje trgovačkog naziva u Naimenovanja
tabu: `_format_trading_names()` podrazumijevano vraća najviše 280 znakova.
Pri skraćivanju prvo se izostavlja ili skraćuje tarifni heading, zatim nazivi
proizvoda, dok se podatak `Faktura: ... (rb. ...)` čuva kad god stane u limit.
Refaktor ne smije promijeniti podrazumijevani `max_chars` na `None`.

Ovo GUI pravilo je dodatno uz strožije XML pravilo iz `rub31_builder.py`:
`Description_of_goods` je jedna linija do 55 znakova, a
`Commercial_Description` najviše tri linije i ukupno do 280 znakova.

---

## 84. Naimenovanja XML import — dokumenti se čitaju iz attached_documents (2026-07-28)

Pri uvozu ASYCUDA XML-a globalni dokumenti moraju se graditi iz kompletne
`NaimenovanjeDraft.attached_documents` liste, ne iz pet pomoćnih
`attached_document1..5` polja. Pomoćna polja su samo ograničeni GUI prikaz:
gube šesti i naredne dokumente i formatiraju reference kao `ŠIFRA (broj)`,
što bi pokvarilo broj `DIS` dokumenta.

PE master iz XML-a služi samo za popunjavanje praznog `attached_document4` na
stavkama sa povlasticom. Već postojeći različiti PE1/PE2/PE3 podaci po stavkama
ne smiju se prepisati master vrijednošću. Nakon toga se zaglavlje ponovo gradi
iz stvarnih item vrijednosti.

Tarifni opis u Naimenovanja servisu koristi lokalni SQLite lookup kao primarni
izvor, ali mora zadržati PostgreSQL fallback iz Windows toka za podbroj i
četvorocifrenu glavu.

---

## 85. InvoiceLine tarifa je uvijek najviše 8 cifara (2026-07-28)

Desetocifreni oblik pripada PostgreSQL/TARIC lookup sloju i ne smije ostati u
`InvoiceLine`. Zajednički `normalize_tariff_number()` uklanja nenumeričke
znakove i svaki kod duži od 8 cifara svodi na prvih 8; kodovi kraći od 8 ostaju
nepromijenjeni jer se smjer nedostajuće cifre ne smije pogađati.

Tok „Učitaj glavnu listu“ je zaseban od standardnog ImportService toka.
`ProductMasterList` može interno proizvesti 10-cifreni bazni zapis, pa
`DeclarationAssembly.load_master_list()` mora normalizovati tarifu pri
kreiranju `InvoiceLine`, prije prikaza u Faktura tabeli i prije grupisanja.

---

## 86. ASYCUDA parity corpus 2024–2026 (2026-07-28)

Referentni ASYCUDA corpus je `H:\New folder\NOVA ASIKUDA`, ali se koriste
isključivo 1.630 XML fajlova iz 2024–2026. Interni datum ima prednost, a kada je
prazan koristi se potvrđeno pouzdani datum izmjene. Sirovi XML, partneri,
fakture i reference dokumenata ne smiju se kopirati u repo niti slati LLM-u;
dozvoljeni su samo agregirani rezultati.

Potvrđene formule su:

`Total_cost = external + internal + insurance + other - deduction`

`Total_CIF = invoice_national + external + insurance + other - deduction`

Broj obrazaca je `1 + ceil((broj_naimenovanja - 1) / 3)`, ne
`ceil(broj_naimenovanja / 3)`.

Dopunske jedinice su dovoljno stabilne za evidence-based automatizaciju, ali
trenutni NAR/PCE i fallback za poglavlja 01–24 imaju dokazano mnogo promašaja.
Dokumenti nisu deterministička funkcija tarife, zemlje, povlastice i postupka;
historija smije dati prijedlog, ne automatski upis bez službenog pravila.

Detaljna metodologija i plan:
`docs/ASYCUDA_PARITY_PROFILE_2024_2026.md`.

---

## 87. Naimenovanja render i dist_client moraju imati jedan aktivan put (2026-07-28)

Aktivni prikaz naimenovanja ostaje
`NaimenovanjaView.render_current_item()` → `_load_current_item()`. Neaktivni
`NaimenovanjeRenderContext` i istoimena slobodna render funkcija iz Phase 4
bili su nepotpun scaffold: nisu imali pozivaoce, nisu pokrivali sva polja forme
i zaobilazili su kanonsko `_set_widget_value()` formatiranje. Ne smiju se
ponovo uključiti bez kompletne migracije svih polja i karakterizacionih testova.

`dist_client` se može pokretati i buildovati kao samostalan root, zato svaki
modul koji root servis uvozi mora postojati i pod `dist_client`. Posebno,
`dist_client/services/naimenovanja/models.py` je obavezan jer ga
`NaimenovanjaService` uvozi pri kreiranju taba.

Ručni izbor tarifnog broja mora ići kroz
`tariff_lookup_requested` → `NaimenovanjaController.on_tariff_changed()`.
View smije prikazati izabranu šifru, ali ne smije direktno mijenjati draft,
emitovati dirty stanje niti sam pokretati tarifnu poslovnu logiku.

---

## 88. "Provjeri" — SHOW_UNCONFIRMED popravlja cor-22 za prijedloge bez izvora (2026-07-28)

Korisnik je prijavio da za proizvod "SUSSINA" (i slične) "Provjeri" dugme ne
daje prijedlog tarife iako postoji jasna istorijska evidencija. Istraga je
otkrila dvoslojan uzrok, direktno vezan za politiku iz §65 (26.07.2026,
"istorijski prijedlog bez potvrđenog izvora se nikad ne prikazuje").

**Sloj 1 — zašto izvor nedostaje**: `TariffMappingService.save_mapping()`
(`services/tariff/tariff_mapping_service.py:937`), putanja koju koristi
SVAKA ručna potvrda/ispravka tarife u aplikaciji (Naimenovanja "Nauči",
Faktura ispravka, agent chat "nauči tarifu" — preko `TariffFacade.learn()`/
`sync_mapping()`), **nikad nije primala niti upisivala `source`/`supplier`
kolonu**. Samo odvojena `learn_from_draft()` (bulk XML učenje) to radi.
Potvrđeno u bazi: `SUSSINA 650/200/1200 tbl.` → `21069098`, korišteno
41-47×, `source`/`supplier` potpuno prazni. Ovaj sloj NIJE popravljen u
ovom fixu (van scope-a — zahtijevalo bi dodavanje `source` parametra kroz
lanac `save_mapping`→`learn`→`sync_mapping` i sve pozivaoce).

**Sloj 2 — pravi Catch-22**: politika §65 suprimira zapis bez izvora PRIJE
nego što uopšte stigne do `TariffValidationDialog` (`decide_tariff_match` →
`SUPPRESS` → `should_show=False`). Ali "ranija ručna potvrda (100%)"
auto-primjena (`_notify_auto_applied_tariffs`) radi preko POTPUNO ODVOJENE
tabele `catalogs.user_feedback`, koja se puni ISKLJUČIVO eksplicitnim
Prihvati/Odbij klikom UNUTAR tog istog dijaloga. Pošto se zapis nikad ne
prikaže, korisnik ga nikad ne može ni potvrditi, pa `user_feedback` nikad
ne dobije zapis — trajno nevidljiv i nepotvrdiv, bez obzira na broj
istorijskih korištenja.

**Fix** (korisnikov eksplicitan izbor: "vrati vidljivost SAMO za ručnu
potvrdu"): `decide_tariff_match()` (`tariff_decision_model.py`) dobija nov
ishod `SHOW_UNCONFIRMED` — kad izvor nedostaje ALI `usage_count ≥
min_usage_for_unsourced_review` (novi prag, 5 — namjerno viši od
`min_usage_for_weak_source`=2, jer je "nema izvora" rizičnije od "slab
izvor"), prijedlog se PRIKAZUJE umjesto potpunog suprimiranja. Postojeća
UI/evidence infrastruktura je već bila spremna za ovo bez ijedne izmjene:
`evidence_from_tariff_decision()` već vraća `DecisionConfidence.UNKNOWN`
za bilo koji zapis bez izvora (nezavisno od outcome-a), što
`TariffValidationDialog._make_row()` već renderuje kao "izvor nepoznat —
nije potvrđena historija", a `_can_accept_all()` već isključuje iz
"Prihvati sve". Samo pojedinačan klik "Prihvati" upisuje u `user_feedback`
— TEK NAKON toga (na sljedećem uvozu) radi auto-primjena.

**Ne slabi politiku §65** — ništa se i dalje ne primjenjuje bez eksplicitne
ljudske potvrde, samo se ta potvrda opet omogućava.

**Sporedan nalaz, nedirano**: baza sadrži i pogrešnu paralelnu mapu
(`SUSSINA` → `38249993`, usage=12 — poraslo sa 2 otkad je §65 politika
aktivna, vjerovatno korisnici ručno unosili pogrešnu tarifu jer im sistem
ništa nije predlagao). `_search_one()` sortira po `usage_count DESC`, pa
ispravan zapis (47) i dalje pobjeđuje kao `best` u `validate_lines()` —
nema praktičan negativan efekat, nije čišćeno.

Testovi: `tests/unit/test_historical_tariff_validation.py` —
`test_unknown_source_never_auto_applied_regardless_of_usage_or_heading`
(preimenovan i prepisan iz `..._never_shown_...`), plus rekonstruisan
`test_search_one_ne_gubi_najjaci_zapis_bez_dobavljaca` (izvoran SUSSINA test
iz 22.07 — sad end-to-end dokazuje `validate_lines()` vraća SHOW_UNCONFIRMED
umjesto praznog rezultata). `tests/unit/test_tariff_validation_dialog.py` —
nov `test_unconfirmed_source_excluded_from_bulk_accept`. Nijedan JSON
fixture case nije trebalo mijenjati (svi postojeći "bez izvora" slučajevi
imaju usage 1-2, ispod novog praga 5).

Puna svita: 1460 passed (1459 + 1 nov test), isti pre-postojeći nepovezani
padovi. `dist_client` test fajlovi (`test_historical_tariff_validation.py`,
`test_tariff_validation_dialog.py`) su bili već zaostali prije ovog fixa
(pre-postojeći drift, nepovezano) — nisu ažurirani da se izbjegne miješanje
sa nepovezanim razlikama; produkcioni kod (`tariff_decision_model.py`,
`historical_tariff_search_service.py`) JESTE ogledan i identičan root-u.
---

## 89. §88 (SHOW_UNCONFIRMED) POVUČEN — korisnik potvrdio strogu politiku bez izuzetka (2026-07-28)

Neposredno nakon §88, korisnik je preispitao i EKSPLICITNO odbacio taj
pristup: "Ne možemo korisniku ponuditi prijedlog a da pritom ne znamo
odakle dolazi, šta je izvor te informacije — jer onda bismo ga mogli
dovesti u zabludu da aplikacija zna, da ne pominjem da greška u tarifiranju
može izazvati kazne." Ovo je jasna, namjerna potvrda da politika iz §65
(26.07) vrijedi BEZ IZUZETKA — čak ni jasno obilježen "izvor nepoznat,
zahtijeva ručnu potvrdu" prikaz (§88) nije prihvatljiv, jer sâmo pojavljivanje
prijedloga u aplikaciji nosi implicitan autoritet koji korisnik ne želi dati
neprovjerenim podacima.

**§88 u potpunosti povučen** — `git revert 8b22281` (commit `aac9b19`),
vraća `decide_tariff_match()` na TAČNO ponašanje iz §65: bez izuzetka
SUPPRESS kad `source` nije poznat, bez obzira na `usage_count`. Test
fajlovi vraćeni na stanje prije §88 istim revert-om.

**Praktična posljedica, prihvaćena svjesno**: SUSSINA (i svaki sličan
"zlatni" istorijski zapis naučen prije nego što je izvor počeo dosljedno
da se bilježi) ostaje TRAJNO nevidljiv u "Provjeri" dijalogu — ne postoji
put unutar tog dijaloga kojim bi ikad mogao dobiti potvrđen izvor, jer
`catalogs.user_feedback` (koji bi mu dao izvor) se puni ISKLJUČIVO iz
klika u tom istom dijalogu, do kojeg zapis sad nikad ne stiže.

**Jedini preostali put naprijed** (nije urađen, čeka korisničku odluku):
Sloj 1 iz §88 istrage — `TariffMappingService.save_mapping()` (putanja za
SVAKU ručnu potvrdu/ispravku tarife: Naimenovanja "Nauči", Faktura
ispravka, agent chat) nikad ne piše `source`/`supplier`. Kad bi ta putanja
počela bilježiti smislen izvor (npr. `"RUCNA_POTVRDA"`) za NOVE ručne
potvrde, takvi zapisi bi ubuduće normalno prolazili kroz postojeće
SHOW_STRONG/SHOW_WEAK grane (imaju izvor, politika ih ne dira) — bez
ikakvog posebnog "neprovjereno" prikaza. Ovo NE bi vratilo vidljivost
postojećih 129 SUSSINA zapisa (nemoguće retroaktivno znati ko ih je
potvrdio), ali bi spriječilo da se isti problem ponovi za svaki budući
proizvod. Za SUSSINA konkretno, jedini preostali put je ručni ispravak
podatka u bazi (van scope-a agenta bez eksplicitnog naloga) ili da
korisnik ubuduće ručno unese tačnu tarifu na fakturi dovoljno puta da,
ako Sloj 1 fix bude urađen, taj NOVI unos dobije izvor i postane vidljiv.

Testovi: puna svita provjerena nakon revert-a — 44/44 u oba dotaknuta test
fajla, isti pre-postojeći nepovezani padovi u punoj suiti.

---

## 90. Zvučna obavještenja označavaju završetak, ne početak procesa (2026-07-28)

Zajednički servis `services/process_completion_sound.py` koristi asinhrone
lokalne WAV signale za tri ishoda: uspjeh, upozorenje i grešku. WAV fajlovi se
generišu u `~/.deklarant_pro/sounds` i reprodukuju preko `winsound` kao fajlovi,
jer Windows sistemski alias može biti nijem kada je sound scheme isključen.
Poziv je best-effort: nedostupan `winsound` ili greška reprodukcije ne smiju
prekinuti poslovni tok niti zamijeniti postojeći modal.

Za Punu automatizaciju i izvoze zvuk se emituje kada je konačni ishod poznat.
Kod ručnog parsiranja fakture emituje se odmah nakon uspješnog parser rezultata,
prije prvog EUR.1/PE ili konfliktnog dijaloga; kasniji završni modal ne smije
ponoviti zvuk. Otkazana Puna automatizacija ostaje bez zvuka, dok parcijalni
rezultat koristi upozorenje.

Funkcionalnost se može isključiti postavljanjem
`PROCESS_COMPLETION_SOUND=false` u aktivnom `.env` fajlu. Root i `dist_client`
moraju zadržati isti servis i ista mjesta poziva. Faktura tab ima objedinjeni i
legacy završni put uvoza; oba moraju emitovati isti zvučni ishod. Legacy put je
aktivan kada je glavna lista već učitana ili parser ne vrati `ImportResult`.

Korisnička postavka `completion_sound_enabled` pripada
`~/.deklarant_pro/settings.json` i mora biti dostupna u
Admin → Podešavanja → Zvučna obavještenja, zajedno sa dugmetom za probu.
AdminView mora imati stvarni SettingsPanel u navigaciji; `get_settings_panel()`
ne smije vraćati SystemPanel. `.env=false` ostaje administratorski override.

EUR.1 modal je sam autoritativni UI okidač: `Eur1QuickDialog.showEvent()` mora
jednom, preko event loopa, pustiti zvuk kada dijalog stvarno postane vidljiv.
Time su pokriveni svi ručni, agent, objedinjeni i legacy putevi koji otvaraju
isti modal, bez oslanjanja na pretpostavljeni callback parsiranja.

---

## 91. Faktura Controller signali ostaju pasivna migraciona infrastruktura (2026-07-29)

Postojanje i povezivanje `FakturaView` signala sa `FakturaTab` handlerima nije
dokaz da je tok migriran u Controller. Signal se aktivira tek kada stari View
handler bude zamijenjen cijelim vertikalnim rezom sa paritet testovima; ne smije
se emitovati na kraju starog handlera jer bi isti proces bio izvršen dvaput.
Bulk primjena validacionih boja mora koristiti `blockSignals`, a `dist_client`
kapija mora stvarno importovati module kao samostalan root, ne samo provjeriti
da fajlovi postoje.

---

## 92. Faktura-3layer spojen u windows — dist_client paritet dopunjen (2026-07-29)

`refactor/faktura-3layer` spojen (fast-forward, 0 konflikata) — infrastruktura
je pasivna/neaktivna (vidi §91), stari View handleri ostaju živi tok.

Prije spajanja popravljen `dist_client/services/faktura/faktura_service.py`
kome je nedostajalo ~55 linija (Faza 2 metode: `parse_number`,
`parse_weight_input`, `format_weight`, `format_issue_counts`,
`extract_import_result_data`) — paritet-test
(`test_faktura_controller.py::TestDistStandalone::test_dist_faktura_modules_match_root`)
nije pokrivao taj fajl u svojoj parametrize listi, sad pokriva.

**Otvoreno, NIJE popravljeno ovim zadatkom**: `dist_client/services/tariff/
tariff_mapping_service.py` je pokvaren 1-linijski compat shim
(`from services.tariff_mapping_service import *`) ka modulu koji nigdje ne
postoji — dok root ima punih 1271 linija (stvaran `TariffMappingService`).
Pre-postojeće na `windows` prije ove grane (`git show windows:...` potvrđuje,
zadnja izmjena `91cfac5`), refaktor ga nije unio. Ako se `dist_client` ikad
build-uje/pokrene kao samostalan root, puca odmah na bilo kom uvozu tarifa
(Faktura, Naimenovanja, agent chat). Poseban follow-up zadatak — sinhronizacija
je veća (1271 linija), van scope-a ovog spajanja.

Puna svita nakon merge-a: 1504 passed, isti pre-postojeći nepovezani padovi
+ gornji `tariff_mapping_service.py` pad.

---

## 93. Tarifni dedup ledger implementiran — čeka DB migraciju (2026-07-29)

Implementiran arhivirani plan (`project_rooms/2026-07-28_tarifno-ucenje-dedup-po-deklaraciji.md`)
nakon što je `refactor/faktura-3layer` spojen (§92) i deblokirao rad.

`DeclarationDraft.draft_uid` (nov UUID field, generisan po draftu, preživljava
nacrt save/load kroz postojeći generički serializer bez dodatnog koda).
`TariffMappingService.learn_with_dedup()` — piše u `catalogs.tariff_learning_ledger`
(draft_uid + line_key), sprječava dupli `usage_count` za istu stavku u istoj
deklaraciji; kod ispravke tarife skida bod sa stare, dodaje novoj (korisnikova
eksplicitna potvrda tog dizajna). Žičeno na dva mjesta koja je korisnik naveo:
`_auto_learn_edits` (Faktura ispravka) i `learn_from_draft` (poziva se iz
`_on_create_naimenovanja`). `_izvezi_xml` radi završno idempotentno
usklađivanje kao sigurnosna mreža.

**Blokirano na DB migraciji**: `deklarant_app` runtime nalog nema DDL
privilegiju (namjerno, sigurnosni hardening) — `database/migrations/
013_tariff_learning_ledger.sql` mora primijeniti neko sa admin/owner pravima
na `dmserver` prije nego ledger stvarno radi. Do tada `learn_with_dedup`
tiho vraća `False` (fail-safe, ne pada) — postojeće ponašanje (bez zaštite od
dupliranja) je nepromijenjeno dok migracija ne uđe.

Sporedan efekat: kopiranje punog `tariff_mapping_service.py` u `dist_client`
(radi dedup funkcije) je usput popravilo pre-postojeći bug iz §92
(`tariff_mapping_service.py` bio 1-linijski pokvaren shim) — potvrđeno,
`dist_client` standalone import test sad prolazi.

Testovi: `tests/unit/test_tariff_learning_ledger.py` — 7/9 prolazi bez baze
(guard klauzule, draft_uid roundtrip, wiring), 2 markirana `@pytest.mark.integration`
padaju sa "relation does not exist" dok migracija ne uđe (očekivano, ne bug).

**Ažuriranje (2026-07-29, isti dan)**: migracija 013 primijenjena na `dmserver`
preko SSH-a (`dmpromet@<trenutna IP>`, `sudo -u postgres psql -d deklarant_pro`).
Dva nova nalaza pri primjeni:
1. `CREATE TABLE` kao `postgres` superuser ne daje automatski prava
   `deklarant_app` runtime nalogu — treba eksplicitan
   `GRANT SELECT, INSERT, UPDATE, DELETE ON catalogs.tariff_learning_ledger TO deklarant_app`
   (sad dio migracije 013). Za buduće migracije koje dodaju tabele: GRANT je
   obavezan korak, ne podrazumijeva se iz sheme.
2. Integration testovi su koristili fiksne `draft_uid`/`naziv_robe` vrijednosti
   bez čišćenja → drugo pokretanje (npr. u punoj svici poslije izolovanog run-a)
   je vidjelo red iz prošlog run-a i lažno padalo. Dodat `clean_ledger_rows`
   fixture (DELETE prije i poslije) u `test_tariff_learning_ledger.py` — realan
   DB cleanup, ne mock (AGENTS.md zabrana).

Nakon oba fixa: `tests/unit/test_tariff_learning_ledger.py` 9/9 prolazi, dvaput
uzastopno (idempotentno). Puna svita: 1514 passed, isti pre-postojeći
nepovezani padovi kao prije (3 failed + 1 error), nula novih regresija.
Dedup ledger je sada potpuno operativan.

---

## 94. Faktura stvarna 3-layer migracija i cleanup su odvojeni checkpointi (2026-07-29)

Pasivni Faktura scaffold nije završen refaktor. Aktivna migracija mora ići
vertikalnim rezovima na posebnoj grani, bez brisanja starog koda, uz očuvanje
`draft_uid`/`learn_with_dedup` toka iz §93. Tek nakon punog testa i korisničkog
E2E odobrenja otvara se zasebna cleanup grana, gdje se svaki stari simbol briše
prema manifestu pozivalaca i zamjene. DB migracija 013 i 9/9 ledger testova su
ulazna kapija. Plan:
`project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md`.

---

## 95. Faktura 3-layer Faza 0 — baseline test kapija dopunjena (2026-07-29)

Faza 0 ne smije mijenjati produkcioni Faktura tok. Dopunjeni su samo
karakterizacioni testovi: tabela → draft roundtrip za sva editabilna polja
uključujući EU broj format i čitanje čiste zemlje iz `Qt.UserRole`, zabrana
nagađanja nedostajućih cifara tarife (`3304990` ostaje takav), te `_on_create_naimenovanja`
mora proslijediti `draft_uid` u `TariffFacade.learn_from_draft()` da dedup ledger
iz §93 ostane zaštićena invarijanta tokom narednih faza.

Ciljani dokaz: 29/29 za `test_faktura_table_roundtrip.py`,
`test_faktura_characterization.py`, `test_tariff_learning_ledger.py`; širi
Faktura/import skup 59/59. Puna suite: 1517 passed, isti pre-postojeći
nepovezani padovi (4 failed + 1 error). Produkcioni kod nije diran.

---

## 96. Faktura 3-layer Faza 1 zatvorena — Controller ledger invarijanta (2026-07-29)

`FakturaTab` ostaje composition root: kreira `FakturaView` i pasivni
`FakturaController` sa `get_draft_fn=lambda: self.view.draft`, bez zasebne
draft reference. Signalni handleri u `FakturaTab` još nisu aktivni produkcioni
tok jer `FakturaView` dugmad i agent i dalje koriste stare View handlere.

Sigurnosna zakrpa: `FakturaController.create_naimenovanja()` mora proslijediti
`draft_uid=getattr(draft, "draft_uid", "") or ""` u
`TariffFacade.learn_from_draft()`. Aktivni View put je to već radio; bez ove
zakrpe bi buduće aktiviranje Controller signala zaobišlo dedup ledger iz §93.
Root i `dist_client` controller moraju ostati identični.

---

## 97. Faktura 3-layer Faza 2 — čisti helperi delegirani u servis (2026-07-29)

Mali HIGH-impact Faza 2 rez završen je bez aktiviranja novih signala: postojeći
`FakturaView._parse_number()`, `_parse_weight_input()` i `_format_issue_counts()`
ostaju compatibility wrapper-i, ali delegiraju u `FakturaService`. Time je
čista logika prebačena u Service sloj bez promjene javnih View metoda.

`FakturaService` mora zadržati paritet sa ranijim View ponašanjem: EU/US parse
brojeva (`1.234,56`, `1,234.56`, `1234.56`), težine punom preciznošću bez
prisilnog zaokruživanja na 3 decimale i issue summary format
`3 bez tarife | 2 bruto < neto | ... | +N tip`. Root i `dist_client` fajlovi
moraju ostati sadržajno isti.

Test kapija: ciljano 78/78 za Faktura service/controller/status/import/ledger;
puna suite 1529 passed uz iste pre-postojeće nepovezane padove (4 failed + 1 error).

---

## 98. Faktura 3-layer Faza 3 — osnovna validaciona boja u servisu (2026-07-29)

`services/faktura/validation_service.py` je usklađen sa stvarnim
`FakturaView._validate_and_color_row()` ponašanjem. Servis vraća neutralni
`RowValidationStyle`: validator result, osnovnu boju reda, tooltip i
per-cell override mapu. Paleta mora ostati postojeća GUI paleta:
`#F9E4E3`, `#FFF4D6`, `#EAF4EE`, `#E6F0F8`.

`FakturaView._validate_and_color_row()` je sada tanji wrapper: servis odlučuje
osnovnu boju i cell override-e, a View i dalje jedini dodiruje Qt tabelu,
`ValidationColorRole`, `validation_cache`, `_apply_country_confidence_color()`
i `_apply_preference_confidence_color()`. Country/preference confidence bojenje
nije premješteno u ovoj fazi jer nosi dodatne poslovne uslove oko povlastice i
dokaza. Root i `dist_client` moraju ostati ogledani.

Test kapija: ciljano 104/104 za širi Faktura validacioni skup; puna suite
1534 passed uz iste pre-postojeće nepovezane padove (4 failed + 1 error).

---

## 99. Faktura 3-layer Faza 4 — ručna validacija aktivirana preko Controller toka (2026-07-29)

Dugme `Provjeri` u Faktura tabu više ne poziva direktno
`FakturaView._on_validate_all`, nego emituje `validate_requested`. Signal hvata
`FakturaTab._on_validate_requested`, koji sinhronizuje tabelu u draft, poziva
`FakturaController.validate_and_color_rows()`, primjenjuje validacione stilove
na Qt tabelu, ažurira `validation_cache` i status bar, prikazuje isti ručni
sažetak validacije i zatim pokreće istorijsku tarifnu provjeru.

Ovo je prvi aktivni View -> Controller -> Service vertikalni rez Faktura taba.
Automatski pozivi `_on_validate_all(auto=True)` nisu prebačeni u ovoj fazi:
ostaju stari pipeline/fallback tok jer su vezani za import, punu automatizaciju
i tajming istorijske validacije. Ostali Faktura signali ostaju pasivna
migraciona infrastruktura dok ne dobiju zasebne test kapije.

`FakturaController.validate_and_color_rows()` mora zadržati stari `color_map`
ugovor, ali sada dodatno vraća `style_map`, `valid_count` i `target_rows` da
handler može popuniti cache i sačuvati selekcijski scope. Testovi koji direktno
emituju signal moraju patchovati `SafeMessageBox` jer aktivni ručni tok sada,
kao prava aplikacija, prikazuje modal.

Test kapija: 69/69 za Faza 0-4 Faktura/ledger skup.

---

## 100. Faktura 3-layer Faza 5 — javni validation API za Agent pipeline (2026-07-30)

Agent Puna automatizacija više ne mora direktno pozivati privatni
`FakturaView._on_validate_all(auto=True)`. Uveden je javni `validate(auto=True)`
adapter na `FakturaTab` i kompatibilni adapter na `FakturaView`, jer trenutni
Agent kod u nekim putanjama i dalje dobija sam View (`AgentController._faktura_view`).
`_puna_auto_pipeline` prvo pokušava `fw.validate(auto=True)`, a privatni
`_on_validate_all(auto=True)` ostaje samo fallback dok svi vanjski pozivaoci ne
pređu na javni `FakturaTab` API.

Ovo nije potpuna migracija automatske validacije u Controller/Service tok.
Namjerno nije promijenjena unutrašnja logika `_on_validate_all(auto=True)`,
generation token, historical worker ni import/puna automatizacija tajming.
Faza 5 je mali adapter rez koji uklanja najvažniju Agent zavisnost od privatnog
View imena, bez promjene poslovnog rezultata.

Test kapija: 36/36 za javni validation API + Puna automatizacija pipeline;
širi Faktura/Agent validacioni skup 107/107 uz `-m "not integration"`.
Pokušaj sa integration ledger testovima imao je 2 DB greške zbog nedostupnog
PostgreSQL servera na `192.168.100.154` / circuit breaker, ne zbog Faze 5.

---

## 101. Faktura 3-layer Faza 6 — javni create-naimenovanja API za Agent pipeline (2026-07-30)

Agent Puna automatizacija više ne mora direktno pozivati privatni
`FakturaView._on_create_naimenovanja(auto=True)`. Uveden je javni
`create_naimenovanja(auto=True)` adapter na `FakturaTab` i kompatibilni adapter
na `FakturaView`, jer trenutni Agent tok još uvijek u nekim putanjama radi sa
View objektom. `_puna_auto_pipeline` prvo pokušava javni
`fw.create_naimenovanja(auto=True)`, a privatni `_on_create_naimenovanja`
ostaje fallback dok se svi pozivaoci ne prebace na javni `FakturaTab` API.

Ovo nije potpuna migracija kreiranja naimenovanja u Controller. Postojeći
legacy View tok ostaje autoritativan za auto režim jer sadrži split draftove,
pre-flight, PE/header sync, reload Faktura/Naimenovanja/Zaglavlje tabova,
ASYCUDA 99 limit, import-service cleanup i `draft_uid` prosljeđivanje u
`TariffFacade.learn_from_draft()`. `FakturaController.create_naimenovanja()`
ostaje zaštićen testom da prosljeđuje `draft_uid`, ali još nije paritetna
zamjena za cijeli View tok.

Test kapija: 38/38 za javni create-naimenovanja API + Puna automatizacija
pipeline; širi Faktura/Agent skup 109/109 uz `-m "not integration"`.

---

## 102. Faktura 3-layer Faza 7 — javni calculate-masses API za Agent pipeline (2026-07-30)

Agent Puna automatizacija više ne mora direktno pozivati privatni
`FakturaView._on_calculate_masses(auto=True)`. Uveden je javni
`calculate_masses(auto=True)` adapter na `FakturaTab` i kompatibilni adapter
na `FakturaView`, jer trenutni Agent tok još uvijek u nekim putanjama radi sa
View objektom. `_puna_auto_pipeline` prvo pokušava javni
`fw.calculate_masses(auto=True)`, a privatni `_on_calculate_masses` ostaje
fallback dok se svi pozivaoci ne prebace na javni `FakturaTab` API.

Ovo nije potpuna migracija masa u Controller/Service tok. Postojeći legacy View
tok ostaje autoritativan za auto režim jer sadrži toolbar parsing, per-invoice
težine, fallback za stavke bez fakture, suspicious fallback guard, poruke,
reload tabele i dirty/data_changed semantiku. Ručni toolbar klik još nije
prespojen na javni signal.

Test kapija: 40/40 za javni calculate-masses API + Puna automatizacija
pipeline; širi Faktura/Agent/mase skup 131/131 uz `-m "not integration"`.

---

## 103. Faktura 3-layer Faza 8 — javni auto-fill API za Agent pipeline (2026-07-30)

Agent Puna automatizacija više ne mora direktno pozivati privatni
`FakturaView._on_auto_fill(auto=True)`. Uveden je javni `auto_fill(auto=True)`
adapter na `FakturaTab` i kompatibilni adapter na `FakturaView`, jer trenutni
Agent tok još uvijek u nekim putanjama radi sa View objektom. `_puna_auto_pipeline`
prvo pokušava javni `fw.auto_fill(auto=True)`, a privatni `_on_auto_fill` ostaje
fallback dok se svi pozivaoci ne prebace na javni `FakturaTab` API.

Ovo nije potpuna migracija auto-popune tarifa u Controller/Service tok.
Postojeći legacy View tok ostaje autoritativan za auto režim jer sadrži undo
snapshot, osnovna polja, TariffFacade preview/commit, selekcijski scope, dijaloge
i render/status semantiku. Ručni toolbar klik još nije prespojen na signal.

Test kapija: 42/42 za javni auto-fill API + Puna automatizacija pipeline;
širi Faktura/Agent/tariff skup 133/133 uz `-m "not integration"`.

---

## 104. Token/context disciplina — podjela CONTEXT.md na evergreen + hronologiju (2026-07-30)

`docs/CONTEXT.md` je narastao na 3380 linija / ~440k tokena pri punom čitanju,
a AGENTS.md je nalagao "OBAVEZNO pročitaj docs/CONTEXT.md prije bilo kakvog
kodiranja" za SVAKOG agenta u SVAKOJ sesiji — klasičan "harness bloat"
(reused input koji se ponavlja bez potrebe). Sekcije 1-14 (evergreen,
cross-cutting pravila bez vezanog datuma) ostale su u `docs/CONTEXT.md`
(sad 301 linija). Sekcije 15-102 (dated, hronološki log pojedinačnih
sesija/faza) premještene su, sa istim brojevima sekcija i sadržajem,
u ovaj fajl (`docs/context/history.md`) — koji se namjerno NE čita cijeli,
nego pretražuje (Grep) po temi/datumu.

**Napomena o §103 iznad**: dok je ova izmjena bila u toku (radna kopija
`docs/context/history.md` još nije bila commitovana), paralelni Codex agent
je na istom `windows` branch-u nezavisno završavao Fazu 8 Faktura 3-layer
refaktora, zatekao novi fajl na disku i ispravno dodao svoj zapis kao "§103"
prateći tek uvedenu konvenciju — a zatim taj rad, uz svoj, commitovao pod
nepovezanom porukom ("uvedi javni auto fill api"). Nema izgubljenog sadržaja,
samo je numeracija poravnata (§103 = Codex Faza 8, §104 = ova izmjena) da se
izbjegne duplikat broja sekcije.

**AGENTS.md izmjene**: "Kontekst projekta" sekcija sad razlikuje dva fajla;
dodana kratka sekcija "Token budget i context disciplina" (princip "ne
prenosi razgovor, prenesi artefakt" — project_room/agent_report umjesto
cijelog chata); Korak 2 sad upućuje nove dated stavke u `history.md`, ne u
`CONTEXT.md`; Korak 3 (agent_report) checklist dobio novo polje "Kontekst
korišćen" (koji veći fajlovi su pročitani u cijelosti i zašto).

**Nije mijenjano**: sadržaj nijedne postojeće stavke (samo premještaj +
promjena brojeva linija), `agent_reports/` arhiva (referenca "Detalji:
docs/CONTEXT.md §N" u starim izvještajima i dalje je tačna po broju
sekcije, samo fizička lokacija sekcije 15+ je sad `docs/context/history.md`
umjesto `docs/CONTEXT.md`), MCP memorija.

Detalji: `agent_reports/2026-07-30_token-disciplina-context-split.md`.

---

## 105. Faktura 3-layer Faza 10 — ručni Auto-popuni klik ide preko signala (2026-07-30)

Ručni klik na dugme `Auto-popuni` u Faktura tabu više ne poziva direktno
`FakturaView._on_auto_fill`, nego emituje postojeći `auto_fill_requested`
signal. `FakturaTab._on_auto_fill_requested` za sada i dalje delegira na isti
legacy View handler, pa se poslovno ponašanje auto-popune tarifa ne mijenja.

Ovo je prvi mali ručni-toolbar rez poslije Agent adapter faza. Namjerno nije
migrirana unutrašnja auto-popuna u Controller/Service i nije uklonjen privatni
fallback, jer `_on_auto_fill` još sadrži undo snapshot, selekcijski scope,
TariffFacade preview/commit, dijaloge i status/render semantiku.

Test kapija: `test_faktura_controller.py` 28/28; širi Faktura/Agent skup
135/135 uz `-m "not integration"`.

---

## 106. Faktura 3-layer Faza 11 — ručni Izračunaj mase klik ide preko signala (2026-07-30)

Ručni klik na dugme `Izračunaj mase` u Faktura tabu više ne poziva direktno
`FakturaView._on_calculate_masses`, nego emituje postojeći
`calculate_masses_requested` signal. `FakturaTab._on_calculate_masses_requested`
za sada i dalje delegira na isti legacy View handler, pa se poslovno ponašanje
raspodjele bruto/neto masa ne mijenja.

Ovo je drugi mali ručni-toolbar rez poslije Agent adapter faza. Namjerno nije
migrirana unutrašnja logika masa u Controller/Service, jer `_on_calculate_masses`
još nosi toolbar parsing, per-invoice raspodjelu, fallback i status/dirty
semantiku.

Test kapija: `test_faktura_controller.py` 29/29; širi Faktura/Agent skup
136/136 uz `-m "not integration"`.

---

## 107. Faktura 3-layer Faza 12 — ručni Kreiraj Naimenovanja klik ide preko signala uz legacy paritet (2026-07-30)

Ručni klik na dugme `Kreiraj Naimenovanja` više ne poziva direktno
`FakturaView._on_create_naimenovanja`, nego emituje postojeći
`create_naimenovanja_requested(False)` signal. Prije aktiviranja signala
ispravljen je `FakturaTab._on_create_naimenovanja_requested`: više ne koristi
parcijalni Controller put, nego delegira na javni `create_naimenovanja(auto=...)`
adapter, koji trenutno čuva autoritativni legacy View tok.

Ova odluka je namjerna sigurnosna mjera. Controller create put još nije paritetna
zamjena za View tok jer legacy handler nosi split draftove, preflight, PE/header
sync, reload Faktura/Naimenovanja/Zaglavlje tabova, ASYCUDA 99 limit i
`draft_uid` učenje. Faza 12 zato mijenja wiring, ali ne mijenja poslovno
ponašanje kreiranja naimenovanja.

Test kapija: `test_faktura_controller.py` 31/31; širi Faktura/Agent skup
138/138 uz `-m "not integration"`.

---

## 108. Faktura 3-layer stabilizacija ručnog toolbar toka (2026-07-30)

Nakon Faza 10-12 potvrđena je mapa ručnih "pametnih" dugmadi u Faktura tabu:
`Provjeri`, `Auto-popuni`, `Izračunaj mase` i `Kreiraj Naimenovanja` sada
sva idu preko Qt signala iz View sloja. Samo `Provjeri` je pravi aktivni
Controller/Service tok; ostala tri signala namjerno delegiraju na javne
legacy adaptere (`auto_fill`, `calculate_masses`, `create_naimenovanja`) da bi
se zadržao produkcioni paritet.

Stabilizacioni fix: `_on_auto_fill_requested` i `_on_calculate_masses_requested`
su ujednačeni sa create handlerom — više ne zovu direktno privatne View metode,
nego javne adaptere na `FakturaTab`. Privatni `_on_*` handleri ostaju ispod
adaptera kao autoritativni legacy tok dok ne dobiju zasebnu migracionu fazu.

Test kapija: `test_faktura_controller.py` 32/32; širi Faktura/Agent skup
139/139 uz `-m "not integration"`. Root/dist_client paritet potvrđen za
`faktura_tab.py` i `faktura_view.py`.

---

## 109. Faktura cleanup/migracioni manifest za legacy handlere (2026-07-30)

Nakon stabilizacije ručnih toolbar signala napravljen je cleanup/migracioni
manifest za naredne faze: `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md`.
Manifest ne mijenja produkcioni kod; zaključava trenutnu mapu javnih ulaza,
legacy `_on_*` handlera, invarijanti i uslova za buduće brisanje.

Ključna odluka: agresivno brisanje legacy handlera nije dozvoljeno prije
paritetnih testova i korisničkog E2E. Preporučeni redoslijed je prvo zaključati
stanje testovima, zatim migrirati mase, potom auto-fill, a create-naimenovanja
workflow ostaviti za kasniju, najoprezniju fazu.

---

## 110. Faktura Cleanup Faza A — test-only zaključavanje javnih ulaza (2026-07-30)

Cleanup Faza A je urađena bez produkcionih izmjena. Dodati/dopunjeni su
characterization testovi koji zaključavaju da Agent pipeline koristi javne
`calculate_masses`, `auto_fill`, `validate` i `create_naimenovanja` metode prije
privatnih `_on_*` fallback-a, dok legacy fallback i dalje ostaje živ za starije
runtime objekte.

Root/dist_client paritet test proširen je na
`gui/tabs/agent/services/import_pipeline_service.py`; test normalizuje samo BOM
razliku (`\ufeff`) jer projekat zabranjuje slijepo mijenjanje BOM encoding-a.
Test kapija: ciljano 50/50; širi Faktura/Agent skup 141/141 uz
`-m "not integration"`.
