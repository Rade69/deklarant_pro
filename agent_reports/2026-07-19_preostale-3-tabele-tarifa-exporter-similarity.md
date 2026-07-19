# Agent Report — 2026-07-19: Preostale 3 tabele — tarifa_nazivi, exporter_xml_index, product_similarity_memory

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `database/migrations/010_drop_tarifa_nazivi.sql` (DROP na live serveru)
- `services/agent/learning/exporter_xml_indexer.py` + dist_client mirror
- `app/run.py` + dist_client mirror
- `pyproject.toml` + dist_client mirror, `requirements-embeddings.txt` (nov)

---

## Status izvora

- `agent_reports/2026-07-19_baza-podataka-audit-katalog.md` — polazna tačka za
  sve tri tabele, aktivan izvor.
- Korisnik je eksplicitno potvrdio plan (delete `tarifa_nazivi`, fix
  `exporter_xml_index`, automatizuj `product_similarity_memory`) prije početka.

---

## GitNexus impact

GitNexus indeks ostaje degradiran za ovaj repo (vidi `docs/CONTEXT.md` §16) —
`gitnexus_impact` nije korišten kao primarni alat. Ručna (grep-based) impact
analiza urađena za svaku izmjenu:

- `find_xml_for_pair`/`find_xml_by_consignee` — 4 pozivaoca identifikovana
  prije izmjene (`faktura_view.py:4828`, `xml_workflow_service.py:138-179`,
  `chat_worker.py:663`, `mcp_facade.py:310`). Izmjena je aditivna (dodat `id`
  u SELECT + poziv `_mark_hit` prije return-a) — potpisi funkcija i povratni
  dict nepromijenjeni, pozivaoci netaknuti.
- `app/run.py::main()` — jedan novi poziv funkcije dodat uz postojeći
  `_start_mcp_server(app)` obrazac, isti thread-based pristup.

Rizik: **LOW** za sve tri izmjene — aditivne, bez promjene postojećih
potpisa/ugovora.

---

## Šta je urađeno

### 1. `tarifa_nazivi` — obrisana (migracija 010)

Isti sigurnosni postupak kao ranija 6 tabela: provjera FK (0), provjera
vlasništva sekvence (`tarifa_nazivi_id_seq` pripada isključivo ovoj tabeli),
backup (DDL + CSV, 0 redova) u `database/backups/2026-07-19_tarifa_nazivi/`,
zatim `DROP TABLE`.

### 2. `exporter_xml_index` — `increment_use_count` povezan (commit `d8ddfc7`)

Dodana `_mark_hit(cursor, conn, row_id)` helper funkcija — poziva se na svih
7 return-tačaka u `find_xml_for_pair` (4 grane: exact_jib, exact_name,
exporter_only, fuzzy) i `find_xml_by_consignee` (3 grane: consignee_jib,
consignee_name, consignee_fuzzy). Svaka grana sad selektuje `id` reda i
inkrementira `use_count`/`last_used` TAČNO tog reda (ne po
exporter_normalized koji bi mogao pogoditi više redova).

### 3. `product_similarity_memory` — sync automatizovan (commit `07de6fb`)

- `app/run.py` (+ dist_client): nova funkcija `_start_product_similarity_sync()`
  pokreće `_run_product_similarity_sync_if_stale()` u pozadinskom daemon
  thread-u pri svakom startu aplikacije (isti obrazac kao `_start_mcp_server`).
  Provjerava `MAX(updated_at)`; ako je starije od 7 dana (ili tabela prazna),
  pokreće `sync_product_similarity_memory()` + `embed_pending()`.
- Otkriven i riješen blokirajući gap: `sentence-transformers` (potreban za
  "local" embedding provider — default kad `PRODUCT_SIMILARITY_EMBEDDING_PROVIDER`
  nije podešen) nije bio ni instaliran ni deklarisan kao zavisnost. Instaliran
  (~1GB sa `torch`), dodan kao opcioni extra `embeddings` u `pyproject.toml`
  (isti obrazac kao postojeći `ocr` extra) + `requirements-embeddings.txt`
  (isti obrazac kao `requirements-ocr.txt`).
- Model `sentence-transformers/all-MiniLM-L6-v2` preuzet i keširan jednokratno
  (kod koristi `local_files_only=True` — radi offline nakon prvog preuzimanja).
- Jednokratni catch-up izvršen ručno: `sync_product_similarity_memory()` →
  23180 → 26404 redova; `embed_pending()` → 18714 redova embedovano, 0
  preostalo bez embeddinga.

---

## Zašto je urađeno

Korisnik se složio sa planom: `tarifa_nazivi` je potpuno mrtva (isti kriterijum
kao ranijih 6 tabela), dok su `exporter_xml_index` i `product_similarity_memory`
stvarno korišćene funkcije koje samo nisu radile kako je zamišljeno — brisanje
bi ih pokvarilo, popravka ih čini korisnima.

---

## Kako je urađeno

- `_mark_hit` koristi `id` (primarni ključ) umjesto rekonstruisanja
  composite ključa (`exporter_normalized`+`consignee_jib`+`consignee_normalized`)
  po grani — jednostavnije i bez rizika da grana 3 (exporter_only, koja ne
  selektuje consignee_normalized) pogrešno inkrementira pogrešan/više redova.
- Staleness provjera u `app/run.py` koristi jednostavan `MAX(updated_at)` upit
  (jeftino, jedan query) prije nego što se pokrene skuplji sync/embed posao —
  većina pokretanja aplikacije će samo preskočiti (no-op).
- `ImportError` na `sentence-transformers` se hvata odvojeno (graceful
  degradation) — sync i dalje radi bez embeddinga ako paket nije instaliran
  na nekoj drugoj mašini/instalaciji.

---

## Šta nije dirano

- `services/agent/chat/declaration_search_service.py` i drugi kod iz
  prethodnog MCP zadatka — netaknuto.
- Gemini/OpenAI embedding putanje u `product_similarity_embedding_service.py`
  — nedirano (korisnik je izabrao lokalni provider).
- `scripts/sync_product_similarity_memory.py`/`embed_product_similarity_memory.py`
  CLI skripte — ostaju netaknute, i dalje se mogu ručno pokrenuti (npr. za
  odmah forsiran refresh bez čekanja na sljedeći start aplikacije).

---

## Verifikacija

```
python -m pytest tests/unit/test_exporter_xml_indexer.py -q
→ 6 passed (postojeći testovi ne pokrivaju DB lookup putanju)

Live provjera protiv prave baze (192.168.0.25):
- find_xml_for_pair(...) → use_count 1→2, last_used ažuriran
- find_xml_by_consignee(...) → use_count 2→3, last_used ažuriran

python -m pytest tests/unit tests/integration -q
→ 689 passed, 44 skipped, 5 xfailed, 2 failed (identično kao prije ovog
  zadatka — isti pretpostojeći Pi/Codex regresija, nepromijenjen brojem)

Live provjera product_similarity_memory:
- prije: 23180 redova, zadnje ažuriranje 2026-05-21
- poslije sync+embed: 26404 redova, 0 bez embeddinga, zadnje ažuriranje danas
- _run_product_similarity_sync_if_stale() pozvan direktno odmah nakon —
  ispravno PRESKOČIO (podaci upravo ažurirani, unutar 7 dana)

python -m py_compile <svi izmijenjeni fajlovi + dist_client mirrors>
→ OK
```

---

## Pronađeni problemi

- `sentence-transformers` nedostajao kao zavisnost — riješeno (vidi gore).
  Ovo je vjerovatno pravi uzrok zašto je sync stao prije ~2 mjeseca (embed
  korak je od tada sigurno padao sa `ModuleNotFoundError` na bilo kojoj
  mašini bez ručno instaliranog paketa).
- Prvi poziv lokalnog embedding modela zahtijeva internet (preuzimanje sa
  huggingface.co) iako je kod pisan za `local_files_only=True` — na potpuno
  svježoj instalaciji bez prethodnog keša, `embed_pending()` će pući dok se
  model ručno ne preuzme jednom (isti korak koji sam ja uradio ovdje). Nije
  automatizovano preuzimanje modela u `_start_product_similarity_sync()` —
  namjerno, da prvi start aplikacije na novoj mašini ne pokuša mrežni poziv
  bez znanja korisnika.

---

## Konflikti / kontradiktorni izvori

Nema.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `9484b0c` | chore(db): ukloni tarifa_nazivi - mrtav widget, nikad wired u GUI |
| `d8ddfc7` | fix(learning): poveži increment_use_count sa find_xml_for_pair/find_xml_by_consignee |
| `07de6fb` | feat(learning): automatizuj product_similarity_memory sync pri startu aplikacije |

---

## Rizici / ograničenja

- `_start_product_similarity_sync()` pokreće posao koji je u testu trajao
  ~12 minuta za pun catch-up (18714 redova). Buduća pokretanja će raditi samo
  inkrementalno (nove/izmijenjene stavke od zadnjeg sync-a) pa će biti brža,
  ali prvo pokretanje na mašini koja dugo nije sinhronizovana može potrajati
  u pozadini — ne blokira UI, ali troši CPU/DB konekciju dok traje.
- Instaliran `torch` (~120MB+ download, veći disk footprint) — ako se ikad
  poželi smanjiti veličinu distribucije, razmisliti o manjem embedding
  modelu ili potpuno odvojenom mikroservisu.

---

## Potreban follow-up

- Za novu instalaciju: dokumentovati da treba `uv sync --extra embeddings`
  ili `pip install -r requirements-embeddings.txt` + jedno pokretanje sa
  internetom da se model preuzme, prije nego offline rad postane pouzdan.
- Razmotriti da li `docs/setup/NOVA_APLIKACIJA_CHECKLIST.md` treba pomenuti
  ovaj korak (nisam ga mijenjao — van scope-a).

---

## Potrebna korisnička potvrda

- Potvrditi da agent chat "slični proizvodi" komanda sada vraća svježije/više
  rezultata (26404 vs ranijih 23180 redova, svi sa embeddinzima).
- Potvrditi da Faktura tab i agent chat XML-template prijedlozi i dalje rade
  normalno (funkcionalno nepromijenjeno, samo se sad prati use_count).
