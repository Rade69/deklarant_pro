# CONTEXT.md — Zajednička memorija za sve agente

> Ovaj fajl čitaju SVI agenti: Claude, Qwen, DeepSeek, i drugi.
> Sadrži ne-trivijalne odluke i pravila koja nisu vidljiva iz samog koda.
> Ažurira ga Claude na kraju svake sesije u kojoj je donesena nova bitna odluka.
> Posljednje ažuriranje: 2026-07-18

---

## 1. Importeri i parseri — kritična pravila

### consumed_paths — OBAVEZNO
Svaki kombinirani importer (Excel+PDF, Invoice+PackingList) MORA postaviti
`consumed_paths=[putanja_potrošenog_fajla]` u `ImportResult`.
Bez toga agent procesira oba fajla zasebno → duplikati stavki u deklaraciji.
Primjeri: Blagić (CASE 1/2), Šumaprom (CASE 1B/2B), Leburic, Invoice+PackingList (CASE 3/4).

### ImportService singleton — zabranjeno
Worker MORA koristiti `ImportService()` (privatna instanca).
NIKAD `get_import_service()` singleton — prouzrokuje race condition u višenitnom uvozu.

### KG Fashion parser
Universal parser za fakture s "K...G...FASHION" D.O.O. u zaglavlju.
Dobavljači: Petite Jolie, Vizzano, Benetton, Sisley, Ambitious, Kese, Bueno, Mod, Jagger.
XLS manifest auto-detekcija → `eur1_suggested` flag (ne `has_origin_statement`).

---

## 2. Tarife i naimenovanja — kritična pravila

### Historijski prijedlozi tarifarnih — samo isti izvoznik
`find_historical_tariff()` MORA imati hard `WHERE exporter = ?` filter.
Nema fallback na druge izvoznike — pogrešne tarife su lošije od praznog polja.
Razlog: različiti izvoznici imaju iste šifre proizvoda ali različite tarife.

### Tariff prefix match
`find_mapping()` prihvata i slučaj gdje je DB kod prefiks traženog koda.
Npr. DB ima `620342` → pokriva `62034211`, `62034219` itd. (varijante boja/veličina).

### Auto-popuni — ne dira povlastice
`TariffMappingService` preskače stavke koje već imaju PE1/PE2/PE3.
Popunjava SAMO tarifni broj, nikad povlasticu ili `eur1_number`.

### _choose_tariff_description filter
`tariff_description1` i `tariff_description2` su isključeni iz `product_names` filtera.
Opisi s brojevima (npr. "27,6 MPa") pogrešno se klasificiraju bez ovog filtera.

### _tariff_heading 4-cifreni fallback
Kad je specifičan opis generički ("ostali", "druge"), koristi 4-cifreni heading iz tarifne baze
umjesto generičkog opisa — daje bolji Rub.31.

---

## 3. ASYCUDA XML export — kritična pravila

### Rb.31 format — strogo 3 linije
ASYCUDA Rub.31 XML izlaz mora ostati max 280 karaktera i najviše 3 linije.
GUI smije prikazati duži pregled radi rada korisnika, ali finalno skraćivanje se radi pri buildanju XML-a.
```
Linija 1: opis robe po tarifi (iz tarifne baze)
Linija 2: komercijalni nazivi iz fakture
Linija 3: broj fakture i datum
```
`_fmt_weight()` uvijek 2 decimale. `Commercial_Description` MORA imati `\n` separator.

### En-dash u tarifnoj bazi
Tarifna baza čuva `–` (U+2013, en-dash) u opisima.
Bez konverzije prikazuje se kao `â` u ASYCUDA. Uvijek konvertovati pri uvozu/izvozu.

### Rb.31 overflow marker
`goods_description` koji sadrži "(+N više)" MORA proći filter — ne tretirati kao grešku.

### Rb.48 — NE kopirati iz historijskog XML-a
Šifra odgođenog plaćanja (`odgodjeno_placanje`) se mijenja godišnje.
Mijenjati samo `TEMPLATE_FIELDS` whitelist u `xml_template_service.py`.

### Attached_doc_item
Svi header dokumenti (faktura, CMR, EUR.1...) moraju biti u `Attached_doc_item`.
Ne samo dokumenti specifični za naimenovanje.

### AttachedDocument normalizacija
`header_attached_documents` i `item.attached_documents` u XML exportu mogu doci kao
`AttachedDocument` objekti ili dict strukture iz GUI/import toka. `AsycudaXMLBuilder`
mora normalizovati oba oblika prije pristupa `code`, `number` i `from_rule`, inace
GUI/EXE moze prikazati samo genericku poruku "Greska pri eksportu".

---

## 4. EUR.1 i povlastice

### Povlastica zahtijeva eksplicitnu potvrdu deklaranta
Parser smije samo detektovati PE2/PE3 izjavu ili potrebu za EUR1 obrascem.
Zemlja porijekla, EU/CEFTA porijeklo, istorija, product master list ili tariff mapping
NISU dokaz za automatsko popunjavanje Rub.36.

Povlastica se primjenjuje tek nakon eksplicitne potvrde deklaranta kroz PE2/PE3/EUR1
dijalog ili rucni unos. Agent i auto-fill smiju prikazati kandidata, ali ne smiju sami
upisati `povlastica`.

### Tok
- Faktura NEMA izjavu o poreklu → EUR.1 dialog (PE1 + broj)
- Faktura IMA izjavu → PE2 dialog (samo zemlja, bez broja)
- `eur1_suggested` flag (ne `has_origin_statement`) određuje koji dijalog se otvara

### Batch uvoz — EUR1 dijalog
`_should_show_eur1_dialog()` vraća False za fakture s `has_origin_statement=True`.
U batch uvozu dijalog se odgađa (defer) — paziti da se ne preskači nepravilno.

### Auto-podjela po zemljama porijekla
`split_draft_by_country()` kreira MultiDraftNavigator ◀▶.
EU zemlje idu zajedno u jedan draft. Mixed-invoice → proporcionalna raspodjela težine.

---

## 5. GUI — poznati bugovi i rješenja

### itemChanged + blockSignals
`setData(ValidationColorRole)` okida `itemChanged` signal 12× po redu.
Bez `blockSignals(True/False)` u `_flush_pending_validation` → beskonačna petlja debounce timera.
Uvijek koristiti `blockSignals` pri masovnim `setData` pozivima.

### scrollToBottom zamjena
`scrollToBottom()` + `_install_bottom_scroll_buffer` zajedno sakrivaju zadnje redove.
Koristiti `EnsureVisible` umjesto `scrollToBottom()`.

### Multi-draft tab sync
`NaimenovanjaView.draft` i Zaglavlje tab moraju se eksplicitno ažurirati pri `_switch_to_draft()`.
`MainWindow._on_tab_changed` uzima `faktura_view.draft` — oba taba moraju primiti novi draft.

---

## 6. Mase i težine

### MassCalculator
Zaokružuje mase na 2 decimale s korekcijom ostatka da bi prikazani zbir bio konzistentan.
Koristiti `weight_guards` servis: `normalize_invoice_key`, `group_lines_by_invoice`.

### Per-invoice raspodjela
`invoice_weights` se čuva u draftu po fakturi, ne globalno.
Dugme "Izračunaj mase" u toolbar-u pokreće per-faktura raspodjelu.

---

## 7. Infrastruktura — sigurnost i arhitektura

### SQL — zabrana f-stringa
NIKAD f-string u SQL upitima. Koristiti isključivo `psycopg2.sql` parametrizaciju.
Pronađena i ispravljena 4 mjesta (Maj 2026) — provjeriti svaki novi SQL.

### Aktivni pipeline
`_puna_auto_pipeline` je jedini aktivni put u agent pipelinu.
`_uvezi_u_deklaraciju` i `_izracunaj_tezine_interno` su mrtav kod — nikad nisu bili aktivni.

### Tool-first agent
Agent prvo koristi lokalni router/tool/servis. Ako tool rezultat ima status `unknown`
ili `needs_review`, LLM ne smije dopuniti tarifni broj, porijeklo, povlasticu ili zaključak.
`TOOL_RESULT` je autoritativan; LLM ga smije samo formatirati za korisnika.

### Lozinka u git historiji
Commit `produkcijska-ociscenja` (Maj 2026) — lozinka je mogla biti eksponirana.
Rotirati DB lozinku ako još nije urađeno!

---

## 8. GitNexus — kako koristiti

GitNexus je mapa koda — zna ko koga poziva, koje funkcije postoje, blast radius promjena.
Index: `deklarant_pro` (18002 simbola, 300 execution flows)

```
Prije izmjene simbola:   gitnexus_impact({target: "ime", direction: "upstream"})
Za razumijevanje koda:   gitnexus_context({name: "ime"})
Za pretragu koncepta:    gitnexus_query({query: "pojam"})
Za provjeru promjena:    gitnexus_detect_changes()
Ako index zastari:       npx gitnexus analyze
```

**Pravilo**: GitNexus odgovara na "šta postoji i ko koga poziva".
Ovaj CONTEXT.md odgovara na "zašto je nešto urađeno tako".

---

## 9. Agent optimizacije (Maj 2026)

### HybridMatchingService — jednom izvan petlje
U `tariff_intent_service.py` (propose_all i propose_by_keyword) `HybridMatchingService()`
se instancira JEDNOM prije petlje i prosljeđuje u `_try_history_match(hybrid, ...)`.
NIKAD unutar petlje — za 30 stavki to znači 30 novih instanci i ~90 suvišnih SQL upita.

### find_batch_by_product_codes — batch SQL
`TariffMappingService.find_batch_by_product_codes(codes)` radi jedan `ANY(ARRAY[...])` upit
za sve product_code-ove odjednom. Koristiti prije petlje u svim mjestima gdje se iterira
po stavkama i traži tarifa po product_code.

### set_analysis_summary — diskretna analiza u status baru
`FakturaView.set_analysis_summary(text, level)` prikazuje rezultat analize u status baru
(lbl_analysis, normalno skriven). Poziva se iz `AgentController._proactive_analysis(lines, fw)`.
Chat poruka: max 2 linije, BEZ prijedloga. Korisnik pita agenta ako hoće — agent ne nudi.

---

## 10. Performansne optimizacije (Maj 2026)

### ManualBatchImportWorker — ručni batch uvoz u background threadu
`services/import_worker.py` — `ManualBatchImportWorker(QThread)` parsira fajlove u pozadini.
NIKAD ne prikazuje dijaloge (EUR1/PE2) — to radi main thread u `_process_batch_records()`.
Koristi privatnu `ImportService()` instancu (ne singleton — race condition).
`_import_multiple_files()` u `faktura_view.py` pokraje worker i odmah vraća kontrolu.

### Packing list matching — O(n×m) → O(n+m)
`importers/packing_list_parser.py`: `code_index` dict za O(1) exact match po product_code.
`packing_norm` lista: nazivi normalizovani jednom prije petlje, ne po svakoj stavci.
`_fuzzy_match_normalized(t1, t2)`: prima već normalizovane stringove — bez redundantnog lower/strip.

### FTS5 indeks za XML arhivu — schema versioning
`declaration_search_service.py`: `items_fts` FTS5 virtual table za `commercial_desc` + `description`.
`_SCHEMA_VERSION = 2` — povećati kad se mijenja shema; `_ensure_index` automatski rebuilda.
`search_by_goods` koristi `MATCH` + `bm25()` ranking umjesto `LIKE %keyword%`.
LIKE fallback ostaje ako FTS5 indeks nije populiran (backward compat).

---

## 11. Windows instalacija — status (2026-05-29)

### Što je pripremljeno
`build_windows.bat`, `deklarant_pro.spec`, `installer/setup.iss`, `build_hooks/version_info.txt`
commitovano u `1cbe4c7` (2026-05-28). Gradi standalone `DeklarantPro.exe` putem PyInstaller.

### Windows klijent (IP: 192.168.100.55, user: "dm promet", pass: "1")
- Python 3.11.9 instaliran ✅
- Fajlovi projekta na `C:\Users\dm promet\Desktop\deklarant_pro` ✅
- **Sljedeći korak:** pokrenuti `build_windows.bat` na Windows računaru

### Procedura licenciranja
Svaka mašina treba zasebnu licencu (machine fingerprint). Detalji u:
`agent_reports/2026-05-24_licenciranje-novih-instalacija.md`
Privatni ključ: `tools/licensing/keys/private_key.pem` — nikad ne commitovati.

### Baza podataka
PostgreSQL je samo na serveru `192.168.0.41`. Windows klijent se SPAJA na server,
ne instalira lokalnu bazu. `.env` na Windows mora imati `DB_HOST=192.168.0.41`.

---

## 12. Encoding i PowerShell bulk izmjene

Tokom Windows portovanja potvrđeno je da bulk skripte koje čitaju/pišu tekst preko
PowerShell `Get-Content`/`Set-Content` mogu proizvesti mojibake u UTF-8/BOM fajlovima.
Za masovne tekstualne izmjene koristiti byte-preserving Python alat ili eksplicitno
`-Encoding utf8`; prije commita obavezno skenirati `Ã`, `Ä`, `Å` i C1 kontrolne znakove.
BOM fajlove ne konvertovati slijepo u LF/bez BOM-a jer dio Windows toka očekuje postojeći format.

---

## 13. Kako ažurirati ovaj fajl

Claude ažurira CONTEXT.md na kraju svake sesije gdje je:
- Donesena nova arhitekturna odluka
- Pronađen i riješen ne-trivijalan bug
- Uvedeno novo pravilo koje nije vidljivo iz koda

Format dodavanja: kratka sekcija u odgovarajućoj temi, max 5-6 linija.
Ne dodavati: šta kod radi (to se vidi iz koda), git historiju, privremeno stanje.

---

## 14. Radni nacrti deklaracije

Radni nacrt se čuva kao prenosivi `DeklarantProDraft` XML na lokaciji koju korisnik izabere.
Ne čuva se u PostgreSQL-u i nema posebno dugme za listu nacrta.
`Uvezi XML` razlikuje Deklarant Pro nacrt od ASYCUDA XML-a: nacrt obnavlja cijeli
`DeclarationDraft`, dok ASYCUDA XML ostaje u postojećem import toku.
Podrazumijevani folder je `Documents/Deklarant Pro/Nacrti`; pamti se posljednja lokacija.

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
