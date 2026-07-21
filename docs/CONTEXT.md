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

---

## 28. PDF pregled po fakturama — stvarna polja šifre deklaracije (2026-07-21)

`PDFFakturaPregled.export()` je čitao nepostojeći `draft.sifra_deklaracije`, pa je svaki
izvoz pregleda po fakturama završavao generičkom greškom prije gradnje PDF-a. Šifra u
naslovu sada se sastavlja iz kanonskih polja `deklaracija_tip`, `deklaracija_oznaka` i
`deklaracija_a`. Regresioni test mora napraviti stvarni `%PDF` fajl, ne samo mockovati
ReportLab poziv.
