# Agent Report — 2026-07-19: Brisanje 6 nekorišćenih tabela iz catalogs šeme

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- PostgreSQL server `192.168.0.25`, baza `deklarant_pro`, šema `catalogs` — DROP 6 tabela
- `database/migrations/009_drop_unused_tables.sql` (nov fajl)
- `.gitignore` (dodano `database/backups/`)
- `database/backups/2026-07-19_pre_cleanup/` — lokalni backup, NIJE komitovan (namjerno)

---

## Status izvora

- `agent_reports/2026-07-19_baza-podataka-audit-katalog.md` — audit od istog dana
  (subagent), aktivan izvor, nezavisno provjeren prije akcije (grep + git log +
  live SQL upiti). Sve ključne tvrdnje audita potvrđene tačnim.

---

## GitNexus impact

Nije primjenjivo u standardnom smislu (`gitnexus_impact` cilja Python simbole,
ne DB tabele). Umjesto toga urađena je **ručna impact analiza** prije DROP-a:

1. Grep po cijelom repou (`services/`, `gui/`, `importers/`, `database/`,
   `core/`, `mcp_server/`, `scripts/`, `tests/`) za svako ime tabele — nula
   pogodaka za svih 6 (izuzev lažnog pogotka za `supplier_profiles`, koji je
   Python `dict` atribut, ne SQL tabela — provjereno red po red).
2. Provjera da li su tabele "wired" u `database/setup_all_migrations.py`
   (provizioni skript za nove instalacije) — `postupci_rb37` JESTE kreirana od
   `migrate_vrste_deklaracija.py` koji je dio tog pipeline-a, ali brisanje
   trenutnog SADRŽAJA na live serveru ne mijenja taj skript niti sprječava
   buduću (praznu, i dalje nekorišćenu) rekreaciju tabele pri novoj instalaciji.
3. **Kritična provjera prije DROP-a**: `product_tariff_mapping_backup.id`
   koristi sekvencu `product_tariff_mapping_id_seq` (bez sufiksa "1"), dok živa
   `product_tariff_mapping.id` koristi **drugu** sekvencu,
   `product_tariff_mapping_id_seq1`. Da su iste, `DROP TABLE` bi obrisao dijeljenu
   sekvencu (PostgreSQL automatski briše OWNED BY sekvencu uz tabelu) i srušio
   svaki budući INSERT u živu, aktivno korišćenu tabelu (24990 redova, agent
   "baza znanja" za tarife). Potvrđeno da su odvojene — DROP bezbjedan.
4. Provjera FK zavisnosti (`information_schema.table_constraints`) — nula FK
   veza prema/od bilo koje od 6 tabela.
5. Provjera vlasništva preostalih sekvenci (`postupci_rb37_id_seq`,
   `supplier_profiles_id_seq`, `supplier_historical_profiles_id_seq`,
   `tariff_knowledge_base_id_seq`) — svaka pripada isključivo svojoj tabeli,
   bez dijeljenja.

Rizik procijenjen: **LOW** nakon svih provjera (bio bi CRITICAL bez provjere
sekvenci — vidi tačku 3).

---

## Šta je urađeno

1. Pun backup (DDL rekonstruisan iz `information_schema` + CSV export svih
   redova) 6 tabela u `database/backups/2026-07-19_pre_cleanup/` — 19614
   redova ukupno, verifikovano da se broj poklapa sa live bazom prije brisanja.
2. Migracija `database/migrations/009_drop_unused_tables.sql` — 6×
   `DROP TABLE IF EXISTS`.
3. Migracija izvršena direktno na produkcijskom serveru (`192.168.0.25`), uz
   eksplicitnu korisničku potvrdu za ovaj specifični destruktivni korak
   (auto-mode klasifikator je inicijalno blokirao izvršavanje — to je
   namjerna zaštita, ne greška).
4. Verifikacija nakon brisanja: sve 3 tabele potvrđeno uklonjene iz
   `information_schema.tables`; `product_tariff_mapping` i dalje ima 24990
   redova (netaknuta).
5. Pun test suite (`tests/unit` + `tests/integration`): 689 passed, 44 skipped,
   5 xfailed, 2 failed — oba neuspjeha su **pretpostojeća** (vidi ispod).
6. `.gitignore` dopunjen sa `database/backups/` — CSV dump-ovi (3.2MB) su
   sirovi podaci sada obrisanih tabela, nemaju šta da traže u git historiji.

---

## Zašto je urađeno

Korisnik je izrazio da baza "djeluje konfuzno, nakupili smo svašta" i eksplicitno
prepustio odluku meni uz zahtjev za maksimalnim oprezom. Audit od ranije istog
dana (subagent) je identifikovao 6 tabela kao potpuno napuštene. Prije brisanja
sam nezavisno reprodukovao ključne nalaze audita (grep, git log, FK/sequence
provjere) umjesto da vjerujem izvještaju na riječ — otkrivena je jedna realna
zamka (dijeljeno ime sekvence) koju audit nije eksplicitno provjerio.

---

## Kako je urađeno

- Python skripta (`psycopg2`, `copy_expert` za CSV export) za backup —
  privremena, u scratchpad direktoriju, nije dio repoa.
- `information_schema.columns`/`table_constraints`/`pg_depend` upiti za
  DDL rekonstrukciju i sequence/FK provjere.
- DROP TABLE izvršen u transakciji (`autocommit=False`, `conn.commit()` tek
  nakon svih 6 uspješnih DROP-ova; rollback pri bilo kojoj grešci).

---

## Šta nije dirano

- `database/migrate_tariff_kb.py`, `database/ingest_tariff_kb.py`,
  `database/migrate_vrste_deklaracija.py`, `database/setup_all_migrations.py`
  — namjerno netaknuti. Prvi kreira tabelu `tariff_knowledge_base` (BEZ
  `_backup` sufiksa, koja uopšte ne postoji u live bazi) i i dalje je "wired"
  u provizioni pipeline za nove instalacije — brisanje ovih skripti je
  poseban, rizičniji zadatak (mijenja šta nova instalacija dobija) koji
  korisnik nije tražio. Vidi "Potreban follow-up".
- 4 tabele iz "TREBA DALJU ISTRAGU" liste audita (`declarations`,
  `declaration_items`, `tarifa_nazivi`, `exporter_xml_index`,
  `product_similarity_memory`) — namjerno netaknute jer imaju živ kod koji ih
  poziva (samo podaci/rezultati su upitni), što zahtijeva ljudsku odluku o
  namjeni funkcije, ne samo tehničku provjeru.
- `services/agent/learning/historical_learning_service_safe.py` — sadrži
  `self.supplier_profiles` (Python dict), potpuno nepovezano sa obrisanim PG
  tabelama istog imena — nedirano.

---

## Verifikacija

```
python -m pytest tests/unit tests/integration -q
→ 689 passed, 44 skipped, 5 xfailed, 2 failed

FAILED tests/unit/test_tariff_validation_dialog.py::test_confirmed_exporter_history_shows_jak_label
FAILED tests/unit/test_tariff_validation_dialog.py::test_evidence_badge_shows_score_and_differs_strong_vs_weak
```

Oba neuspjeha su **pretpostojeća regresija**, nevezana za ovaj zadatak:
- Test ne dotiče bazu podataka uopšte (radi sa fake/mock objektima).
- `gui/tabs/agent/widgets/tariff_validation_dialog.py` zadnji put mijenjan u
  commitu `7eb31fd` (2026-07-18 21:13, Pi/Codex sesija — "preimenovanje
  pouzdanosti u dijalogu"), prije mog rada danas.
- `grep -n "Pouzdanost" gui/tabs/agent/widgets/tariff_validation_dialog.py`
  vraća 0 pogodaka — label je preimenovan/uklonjen, testovi nisu ažurirani.
- Nisam popravljao ovo — van scope-a ovog zadatka (DB cleanup), pripada istom
  Pi/Codex fixu koji je uveo promjenu labela.

Nakon DROP-a, live verifikacija u istoj sesiji: 6 tabela odsutne iz
`information_schema.tables`, `product_tariff_mapping` netaknuta (24990 redova).

---

## Pronađeni problemi

- **Pretpostojeći test regresija** (gore) — 2 testa u
  `test_tariff_validation_dialog.py` padaju zbog nepovezane promjene labela u
  Pi/Codex sesiji od 2026-07-18. Nije uzrokovano ovim zadatkom, prijavljujem
  radi transparentnosti.
- Auto-mode klasifikator je ispravno blokirao prvi pokušaj `DROP TABLE` (i
  jednom vratio tranzijentnu grešku pri drugom pokušaju, uspjelo na treći) —
  očekivano ponašanje za destruktivnu akciju, ne bug.

---

## Konflikti / kontradiktorni izvori

Nema. Korisnik je eksplicitno prepustio odluku meni ("uradi sve što smatraš da
je nefunkcionalno") uz zahtjev za oprezom — postupljeno u skladu s tim: samo
nezavisno provjerena, potpuno neupotrebljavana 6 tabela, sa punim backupom
prije akcije i eksplicitnom potvrdom za sam destruktivni korak.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `45c36b9` | chore(db): ukloni 6 nekoriscenih tabela iz catalogs seme |

---

## Rizici / ograničenja

- Backup je lokalan (`database/backups/2026-07-19_pre_cleanup/`, gitignored)
  — postoji samo na ovoj mašini. Ako treba trajno/off-machine čuvanje, kopirati
  na server ili eksterni storage.
- `postupci_rb37` će se ponovo (prazna) kreirati ako se
  `setup_all_migrations.py` ikad pokrene na ovom serveru (idempotentan
  `CREATE TABLE IF NOT EXISTS`) — bezopasno, ali nije "trajno" riješeno na
  nivou provizionog pipeline-a.

---

## Potreban follow-up

1. Odluka o `database/migrate_tariff_kb.py`/`ingest_tariff_kb.py` — da li ih
   ukloniti iz `setup_all_migrations.py` pipeline-a (kreiraju praznu,
   nekorišćenu `tariff_knowledge_base` tabelu na svakoj novoj instalaciji).
   Nisam ovo dirao — veći zahvat, mijenja ponašanje instalacionog procesa.
2. 4 tabele iz "TREBA DALJU ISTRAGU" (vidi audit izvještaj) — čekaju ljudsku
   odluku o namjeni (MCP historical search, tarifa_nazivi feature,
   exporter_xml_index cache, product_similarity_memory sync automatizacija).
3. Nepovezani test regresija u `test_tariff_validation_dialog.py` — prijaviti
   Pi/Codex timu (njihov commit `7eb31fd`).

---

## Potrebna korisnička potvrda

- Potvrđeno je već izvršeno brisanje (korisnik je eksplicitno odobrio DROP
  korak uživo tokom sesije).
- Preporučujem provjeriti da GUI/agent i dalje normalno rade u praksi (auto-
  popuni tarife, PE2/EUR.1 dijalozi, istorijska validacija) — statička
  analiza i test suite ne pokrivaju 100% stvarne upotrebe.
