# Agent Report — Audit PostgreSQL šeme `catalogs`

**Datum:** 2026-07-19
**Agent:** Claude (istraživački zadatak, bez izmjena koda/baze)
**Scope:** Sve tabele u PostgreSQL šemi `catalogs` (baza `deklarant_pro`, server 192.168.0.25) — isključivo SELECT upiti + grep po `services/`, `gui/`, `importers/`, `database/`, `core/`, `mcp_server/`, `scripts/`, `tests/`; `dist_client/` isključen iz klasifikacije (runtime mirror), spominje se samo kad se razlikuje.

Napomena: zadatak je naveo "34 tabele", ali priložena lista sadrži **36** naziva —
obrađeno je svih 36, brojka u nazivu zadatka je preneseno kako je primljeno.

---

## Sažetak

Baza nije haotična koliko se činilo — većina tabela (26 od 36) je aktivno korištena
u tekućem kodu i ima podatke koji rastu (`created_at`/`last_used` do danas ili blizu
danas). Pronađeno je **5 jasno napuštenih tabela bez ijedne reference u kodu**
(`product_tariff_mapping_backup`, `tariff_knowledge_base_backup`, `supplier_profiles`,
`supplier_historical_profiles`, `postupci_rb37`) — sve bez FK zavisnosti, sve sigurne
za brisanje sa čisto tehničke strane. Dodatno su otkrivene **2 tabele s aktivnim kodom
ali bez ijednog reda podataka** (`declarations`/`declaration_items` — MCP historical
search, i `tarifa_nazivi` — praksa naziva robe): kod postoji i poziva se, ali funkcija
je efektivno mrtva jer nema šta da vrati. `declaration_drafts` je poseban slučaj —
eksplicitno napuštena po dokumentovanoj odluci (agent_report 2026-06-14: PostgreSQL
nacrti zamijenjeni XML fajl-baziranim sistemom jer radni tok ne smije zavisiti od
dostupnosti servera). `product_similarity_memory` i `product_tariff_mapping` **nisu**
duplikat — prva je vektorski embedding indeks izgrađen IZ druge (`source_table =
"catalogs.product_tariff_mapping"` hardkodovano u servisu), za semantičku pretragu u
agent chatu; podaci u njoj su zastarjeli (zadnja sinhronizacija 2026-05-21, dok
`product_tariff_mapping` raste do danas) jer sync nije automatski nego se pokreće
ručnim skriptama.

---

## Tabela nalaza (svih 36)

| Tabela | Row count | Klasifikacija | Napomena |
|---|---|---|---|
| `agent_sessions` | 168 | AKTIVNA | `gui/tabs/agent/session_manager.py`, raste do 2026-07-18 |
| `carinske_ispostave` | 97 | SAMO ČITANJE | statični šifarnik, `sifarnici_service.py`, `zaglavlje_view.py` |
| `carinski_dokumenti` | 28 | AKTIVNA | FTS pretraga dokumenata u agent chatu (`chat_worker.py`), indeksirano jednokratno 2026-05-02 |
| `carinski_postupci` | 148 | SAMO ČITANJE | statični šifarnik, koristi ga `sifarnici_view/controller` |
| `declaration_drafts` | 0 | MRTAV/NAPUŠTEN | eksplicitno zamijenjen XML-fajl pristupom (vidi analizu ispod) — 0 referenci u aktivnom kodu |
| `declaration_items` | 0 | AKTIVNA kod, PRAZNA tabela | `mcp_server/tools/declaration_search.py` čita, ali puni je samo one-off `database/migrate_mappings.py` koji očito nikad nije pokrenut (0 redova) |
| `declarations` | 0 | AKTIVNA kod, PRAZNA tabela | isto — MCP server se pokreće s aplikacijom (`app/run.py:_start_mcp_server`), ali istorijska pretraga uvijek vraća prazno |
| `deklaranti` | 2 | AKTIVNA | `zaglavlje_view.py`, `sifarnici_service.py` |
| `drzave` | 249 | AKTIVNA | `eur1_quick_dialog.py`, `services/countries_cache.py`, importeri |
| `exporter_xml_index` | 1050 | AKTIVNA (kod), STAGNIRA (podaci) | bulk uvezeno 2026-06-13, ali `use_count`/`last_used` identični za sve redove od tada — cache se od uvoza nije nijednom "pogodio" (vidi napomenu) |
| `incoterms` | 11 | SAMO ČITANJE | `asycuda_xml_builder.py`, `sifarnici_service.py` |
| `inspection_rules` | 1098 | AKTIVNA | `tariff_controls_service.py`, `inspection_service.py`, ažurirano 2026-04-14/15 |
| `izjave_o_poreklu` | 14 | AKTIVNA | `services/origin_statement_detector.py` (i duplikat `services/tariff/origin_statement_detector.py` — vidi "Šta nije provjereno") |
| `izvoznici` | 2116 | AKTIVNA | CRUD kroz GUI, importeri, EUR.1 dijalozi |
| `pakovanja` | 356 | AKTIVNA | `naimenovanja_view.py`, `packing_list_parser.py`, importeri |
| `postupci_rb37` | 0 | NEMA REFERENCI (u aplikaciji) | samo unutar `database/migrate_vrste_deklaracija.py` (kreiranje + vlastiti `verify()` report); GUI/servisi je ne čitaju nikad |
| `povlastice` | 14 | AKTIVNA | najviše referenci od svih šifarnika (68 fajlova) — decision servis, validacija, agent |
| `prethodni_dokumenti` | 35 | AKTIVNA/SAMO ČITANJE | `naimenovanja_view.py`, `populate_db.py` |
| `prilozeni_dokumenti_sifre` | 163 | AKTIVNA | `zaglavlje_view.py`, `zaglavlje_service.py` |
| `product_similarity_memory` | 23180 | AKTIVNA (ali zastarjeli podaci) | embedding indeks nad `product_tariff_mapping`, koristi ga `chat_intent_handler.py` preko `similar_products_analysis_service.py`; zadnja sinhronizacija jednokratna 2026-05-21 |
| `product_tariff_mapping` | 24990 | AKTIVNA | glavna "baza znanja" za auto-popunjavanje tarifa; raste do 2026-07-18 (danas) |
| `product_tariff_mapping_backup` | 3871 | NEMA REFERENCI | **0 pogodaka bilo gdje u repou** (uklj. `dist_client`, migracije, dokumentaciju); zamrznuto 2026-03-24 – 2026-04-06 |
| `quota_snapshot_items` | 63 | AKTIVNA | `services/quota_service.py`, `gui/tabs/sifarnici/quota_panel.py`, raste do 2026-07-18 |
| `quota_snapshots` | 9 | AKTIVNA | isto, UINO kvote |
| `regionalni_centri` | 4 | SAMO ČITANJE | statični šifarnik, FK iz `carinske_ispostave` |
| `supplier_historical_profiles` | 4 | NEMA REFERENCI | 0 pogodaka u `.py` kodu; zamrznuto 2026-04-09 (jedan batch) |
| `supplier_profiles` | 5 | NEMA REFERENCI | jedini pogodak (`historical_learning_service_safe.py`) je LAŽAN — `self.supplier_profiles` je in-memory Python dict, ne PG tabela; zamrznuto 2026-04-09 |
| `tarifa_nazivi` | 0 | AKTIVNA kod, PRAZNA tabela | `database/db.py:get_nazivi_robe_za_tarifu/search_nazivi_robe`, poziva ih `gui/widgets/db_widgets.py`, ali tabela nikad nije napunjena — funkcija u praksi uvijek vraća `[]` |
| `tariff_controls` | 701 | AKTIVNA | `faktura_view.py`, `naimenovanja_view.py`, `tariff_controls_service.py` |
| `tariff_knowledge_base_backup` | 15728 | NEMA REFERENCI | 0 pogodaka bilo gdje; vidi detaljnu analizu — vjerovatno stari koncept prije `product_tariff_mapping`, ručno preimenovan na serveru (naziv se ne pojavljuje nigdje u git historiji) |
| `tipovi_deklaracija` | 3 | AKTIVNA | `zaglavlje_view.py:_load_tipovi_deklaracija_from_db` → `_populate_oznaka_combo` |
| `user_feedback` | 454 | AKTIVNA | `tariff_feedback_service.py`, raste do 2026-07-17 |
| `uvoznici` | 678 | AKTIVNA | CRUD kroz GUI, isti obrazac kao `izvoznici` |
| `vrste_deklaracija` | 7 | AKTIVNA | `zaglavlje_view.py`, `zaglavlje_service.py` |
| `vrste_prijevoza` | 9 | AKTIVNA | `zaglavlje_view.py`, `sifarnici_service.py` |
| `zvanicna_tarifa` | 12686 | SAMO ČITANJE | zvanična carinska tarifa, `tariff_facade.py`, RAG servisi |

---

## Detaljna analiza preklapajućih tabela

### `product_similarity_memory` vs `product_tariff_mapping` vs `tariff_knowledge_base_backup`

**`product_similarity_memory` NIJE duplikat `product_tariff_mapping`-a.** Dokaz:
`services/agent/learning/product_similarity_memory_service.py:75`:

```python
class ProductSimilarityMemoryService:
    source_table = "catalogs.product_tariff_mapping"
```

Ovo je vektorski embedding indeks (kolone `embedding`, `text_for_embedding`,
`embedding_model`) koji se **puni iz** `product_tariff_mapping` preko
`scripts/sync_product_similarity_memory.py` i `scripts/embed_product_similarity_memory.py`,
za potrebe semantičke ("slični proizvodi") pretrage. Read-put je uveden u
`services/agent/chat/similar_products_analysis_service.py`, koji je uvezen u
`gui/tabs/agent/services/chat_intent_handler.py` — dio je žive agent-chat funkcionalnosti.
Podaci su, međutim, zastarjeli: sve vremenske kolone pokazuju jedan dan
(2026-05-21), dok `product_tariff_mapping` kontinuirano raste do danas (2026-07-18) —
sync nije automatski, pokreće se ručno i izgleda da nije pokretan ~2 mjeseca.

**`tariff_knowledge_base_backup` JESTE zastarjeli/napušteni koncept.** Dokazi:
- Nula pogodaka za `tariff_knowledge_base_backup` bilo gdje u repou (kod, migracije,
  dokumentacija, git historija — provjereno i `git log -S`).
- `database/migrate_tariff_kb.py` i `database/ingest_tariff_kb.py` još postoje u
  repou, ali oba ciljaju tabelu `catalogs.tariff_knowledge_base` (**bez** `_backup`
  sufiksa) — ta tabela više ne postoji u trenutnoj šemi.
- Git commit `9db8b46` (2026-04-12, poruka: *"refactor(services): Faza A — brisanje
  neukorišćenih fajlova"*) briše `services/tariff_kb_ingestor.py` uz obrazloženje
  "CLI alat, nije servis" i "bez ijednog importera" — to je bila skripta koja je
  punila `catalogs.tariff_knowledge_base`.
- Zaključak: tabela `tariff_knowledge_base` je u nekom trenutku (van git kontrole,
  direktno na serveru) preimenovana u `tariff_knowledge_base_backup` — vjerovatno
  kad je `product_tariff_mapping` postao kanonska "baza znanja"
  (`docs/decisions/003-multi-spedicija-prilagodba.md:19`: *"Baza znanja:
  catalogs.tarifa_nazivi, product_tariff_mapping — izgrađeno iz njihove istorije"*
  — `tariff_knowledge_base` se tu više ne spominje). Nijedan trenutni servis je
  ne dotiče.

### `supplier_profiles` vs `supplier_historical_profiles`

**Obje su NEMA REFERENCI — ovo NIJE slučaj "aktivna vs zastarjela verzija",
nego dvije potpuno napuštene tabele.** Dokazi:
- Grep za `supplier_profiles`/`supplier_historical_profiles` u `.py` fajlovima
  vraća samo `services/agent/learning/historical_learning_service_safe.py`, ali
  svih 14 pogodaka je `self.supplier_profiles` — atribut Python klase
  (`Dict[str, SupplierProfile]`), **ne** PostgreSQL tabela. Nijedan SQL upit
  (`SELECT`/`INSERT`/`UPDATE ... supplier_profiles`) ne postoji nigdje u kodu.
- Trenutna funkcionalnost "profil dobavljača" (`services/agent/learning/
  supplier_profiling_service.py`) gradi profil **dinamički u letu** iz
  `catalogs.exporter_xml_index` (linije 147, 377: `FROM catalogs.exporter_xml_index`)
  — ne dotiče PG tabele `supplier_profiles`/`supplier_historical_profiles` uopšte.
- Nijedna migraciona skripta u `database/` ne kreira ove dvije tabele — moraju biti
  ručno kreirane/napunjene na serveru, van git kontrole.
- Obje imaju identičan obrazac: sve vrijeme upisane u istoj minuti 2026-04-09
  (`learned_at` min=max), 5 i 4 reda — jednokratan eksperiment/uvoz koji nikad
  nije povezan sa živim kodom.

---

## Preporuke

**Ovo je preporuka za ljudsku odluku — nije akcioni plan koji se izvršava
automatski. Prije brisanja: napraviti `pg_dump` snapshot cijele šeme `catalogs`
kao sigurnosnu kopiju.**

### SIGURNO ZA BRISANJE (0 referenci u kodu, 0 FK zavisnosti, podaci zamrznuti mjesecima)

| Tabela | Zašto |
|---|---|
| `product_tariff_mapping_backup` | 0 pogodaka u cijelom repou; zamrznuto od 2026-04-06 |
| `tariff_knowledge_base_backup` | 0 pogodaka; dokazano napušten koncept prije `product_tariff_mapping` |
| `supplier_profiles` | 0 pogodaka (jedini "pogodak" je lažan, in-memory dict); zamrznuto od 2026-04-09 |
| `supplier_historical_profiles` | isto kao gore |
| `postupci_rb37` | koristi je samo migraciona skripta u vlastitom `verify()` reportu, GUI/servisi je nikad ne čitaju |
| `declaration_drafts` | eksplicitno zamijenjena XML-fajl pristupom po dokumentovanoj odluci (2026-06-14) |

Provjereno: FK upiti nad `information_schema` pokazuju da nijedna od ovih 6 tabela
nije referencirana stranim ključem iz druge tabele u šemi `catalogs`.

### TREBA DALJU ISTRAGU (kod postoji, ali nešto ne štima)

| Tabela | Šta provjeriti |
|---|---|
| `declarations` / `declaration_items` | MCP server se pokreće s aplikacijom i upiti postoje, ali tabele su prazne — pitanje za vlasnika: da li se `database/migrate_mappings.py` treba pokrenuti da napuni istorijske podatke, ili je MCP "historical declaration search" alat napušten pa i te tabele treba ukloniti zajedno s njim |
| `tarifa_nazivi` | kod (`db.py` + `db_widgets.py`) je živ i pozvan iz GUI-a, ali tabela je prazna — ili nikad nije bila napunjena, ili je izbrisana; provjeriti da li je "praksa naziva robe" feature namjerno ugašen |
| `exporter_xml_index` | 1050 redova iz bulk uvoza 2026-06-13, ali nijedan `use_count`/`last_used` se od tada nije promijenio — provjeriti da li lookup logika u `exporter_xml_indexer.py` uopšte pogađa cache u produkciji |
| `product_similarity_memory` | sync skripte postoje ali očito se ne pokreću redovno (~2 mjeseca zastoja) — odlučiti da li automatizovati (cron/scheduled task) ili ostaviti kao povremeni alat |

### NE DIRATI (aktivno u produkciji, rastu do danas)

`agent_sessions`, `product_tariff_mapping`, `quota_snapshots`, `quota_snapshot_items`,
`user_feedback`, i svi statični šifarnici koje čita GUI (`drzave`, `izvoznici`,
`uvoznici`, `povlastice`, `pakovanja`, `tariff_controls`, `inspection_rules`, itd.)

---

## Šta nije provjereno

- **Nije pokretana aplikacija uživo** — klasifikacija "AKTIVNA" je zasnovana na
  statičkoj analizi (grep + poziv-lanac), ne na stvarnom trasiranju izvršavanja;
  moguće je da neki "aktivni" kod put nikad ne biva pozvan u praksi (npr. rijetko
  korišten meni/dugme).
- **`services/origin_statement_detector.py` i `services/tariff/origin_statement_detector.py`
  su bajt-identični duplikati**, oba aktivno uvezena iz različitih mjesta — ovo je
  nalaz o duplikaciji koda, ne o duplikaciji tabele, van je striktnog scope-a ovog
  audita (samo `catalogs` šema) ali vrijedi spomenuti jer se oba oslanjaju na
  `izjave_o_poreklu`.
- **Nije provjereno da li postoje drugi konzumenti van ovog repozitorija**
  (npr. eksterni skript, ASYCUDA integracija, ili ručni SQL koji korisnik
  povremeno pokreće direktno kroz psql/pgAdmin) — audit pokriva samo ono što je
  u git repozitoriju `deklarant_pro`.
- **Veličina na disku (bytes) nije mjerena** — fokus je bio na broj redova i
  reference u kodu, ne na fizički prostor koji tabele zauzimaju.
- **`dist_client/` kopija koda nije sistematski upoređena red-po-red** sa
  glavnim stablom za svaku tabelu — provjereno je samo par slučajeva gdje je
  razlika bila relevantna (npr. `exporter_xml_indexer.py` postoji identično
  na oba mjesta).
- **Nije rekonstruisano ko/kada/zašto je ručno kreirao/preimenovao**
  `supplier_profiles`, `supplier_historical_profiles` i
  `tariff_knowledge_base_backup` direktno na serveru (van git kontrole) — ovo je
  hipoteza potkrijepljena posrednim dokazima (git historija za srodne fajlove,
  vremenske oznake), ne direktno potvrđena.
