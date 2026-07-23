## Datum
2026-07-23

## Agent
Claude Code (Sonnet 5)

## Scope
- `services/tariff/tariff_tree_service.py` + `dist_client/` kopija
- `services/agent/chat/tariff_history_analysis_service.py` + `dist_client/` kopija
- `database/migrations/011_pg_trgm_product_similarity.sql` (novo)
- `database/migrations/012_pg_trgm_zvanicna_tarifa_i_declaration_items.sql` (novo)
- `tests/unit/test_tariff_tree_service_db_path.py`,
  `tests/unit/test_tariff_history_analysis_db_path.py` (novi)
- AST-based skeniranje cijele kodne baze (bez izmjena — negativan rezultat)

## Status izvora
Direktan nastavak `agent_reports/2026-07-23_no-such-table-tarifa-2026-fix.md` —
korisnik zatražio sistematsko traganje za istom klasom bugova (§44 → §45 u CONTEXT.md).

## GitNexus impact
- `tariff_tree_service.py::get_tree`: LOW pre-provjera, 8 impactedCount preko chat_intent_handler
  (agent chat hijerarhijska pretraga)
- `tariff_history_analysis_service.py::_sqlite_history`: LOW pre-provjera, 7 impactedCount
  preko `analiziraj_tarifne_historiju` → `chat_intent_handler.py`
- Post-commit `gitnexus_detect_changes`: risk_level MEDIUM (2 pogođena procesa: `get_tree →
  _get_conn`, `get_tree → _row_to_dict`) — oba očekivana i namjeravana (DB_PATH izmjena
  direktno utiče na `_get_conn`), nema neočekivanih kolateralnih promjena

## Šta je urađeno
Tri ciljane, bounded provjere po istom obrascu kao jučerašnji rad (§43/§44), na zahtjev
korisnika koji je eksplicitno tražio "šta bi bilo dobro istražiti" u kodnoj bazi od 150k+
linija:

**a) `__file__`-relativni DB_PATH bez frozen-svijesti** — grep pronašao 2 dodatna runtime
modula (isključujući migracione/admin skriptove van scope-a jer se ne pokreću iz shipped
`.exe`-a):
- `tariff_tree_service.py` — putanja pogrešna ČAK I U DEV MODU (pogrešan broj `..`,
  vjerovatno ostatak nakon premještanja fajla u podfolder). Popravljeno + potvrđeno da sad
  vraća stvarne podatke (`get_children('85')` → `['8501', '8502', '8503']`).
- `tariff_history_analysis_service.py` — ispravno u dev modu, bez frozen fallback-a.

**b) AST provjera dupliciranih metoda/funkcija** — napisan Python skript (ast.parse po
fajlu, provjera duplih imena unutar iste klase/modula, isključujući `@overload`/
`@property.setter` legitimne slučajeve) preko cijelog projektnog koda. **Rezultat: nula
pogodaka u našem kodu** (2 lažna pozitivna samo u vendorisanim `.venv` bibliotekama).

**c) ILIKE upiti bez pg_trgm indeksa** — grep 30 ILIKE poziva u `services/`, provjera
veličine i EXPLAIN ANALYZE za svaku ciljanu tabelu. 3 dodatne tabele potvrđene kao
Seq Scan i popravljene novim GIN trigram indeksima (migracije 011, 012).

## Zašto je urađeno
Korisnik je eksplicitno tražio da se, s obzirom na veličinu kodne baze, sistematski
potraži ISTA KLASA bugova koju smo već pronašli (ne nasumičan pregled) — potvrđena
hipoteza da "jedan pronađen primjer ⇒ vrijedi provjeriti cijelu klasu" daje visok prinos
po uloženom vremenu, u odnosu na opšti code review.

## Kako je urađeno
- (a): `grep` za `os.path.dirname(__file__).*database` kroz cijeli repo, filtrirano na
  runtime servisne module (isključeni migracioni skriptovi), provjera ispravnosti putanje
  direktnim pokretanjem (`python -c "from services... import m; print(m.DB_PATH,
  os.path.exists(...))"`), pa fix istim `_resolve_db_path()` obrascem kao juče.
- (b): Python AST skript — dvije iteracije (prva slučajno uhvatila stari `dist/
  DeklarantPro/_internal/torch/...` leftover PyInstaller build-artefakt sa lažnim
  pozitivnim `@overload` funkcijama; druga scoped samo na projektne foldere +
  isključeni `@overload`/`@property` dekoratori).
- (c): `grep "ILIKE %s"` u `services/`, `EXPLAIN ANALYZE` za svaku ciljanu tabelu preko
  žive PostgreSQL konekcije, nove migracije za tabele gdje je Seq Scan potvrđen (>9000
  redova); male referentne tabele (stotine redova) namjerno preskočene.

## Šta nije dirano
- Migracioni/admin skriptovi (`database/migrate_*.py`, `scripts/merge_izvoznici_duplikati.py`)
  sa istim `__file__`-relativnim obrascem — pokreću se ručno preko `python script.py`, ne
  iz frozen `.exe`-a, pa ih ovaj bug ne pogađa u praksi.
- Male referentne tabele (`izvoznici`, `uvoznici`, `drzave`, `carinski_postupci`) —
  seq scan tamo je već sub-milisekundan, indeks ne bi donio mjerljivu korist.
- `database/migrations/008-010` nedostaju u `dist_client/database/migrations/` (pre-postojeći
  gap, otkriven usput, van scope-a ovog zadatka — vidi "Potreban follow-up").
- `dist/DeklarantPro/` leftover build folder (stari PyInstaller izlaz sa torch bibliotekom)
  — otkriven kao izvor šuma u prvom pokušaju AST skeniranja, nije obrisan (nije moje da
  brišem korisnikove fajlove bez pitanja).

## Verifikacija
- `tariff_tree_service.py`: `get_children('85', limit=3)` prije fixa vraćalo prazno/gresku,
  poslije vraća `['8501', '8502', '8503']` (potvrđeno direktnim pozivom)
- 5 novih testova (`_resolve_db_path` standardna/frozen/regresija na pogrešan broj `..`)
- `EXPLAIN ANALYZE` prije/poslije za sve 3 nove migracije: 76ms→0.88ms, 38.6ms→0.69ms,
  25.5ms→0.44ms (svi Seq Scan → Bitmap Index Scan)
- Pun test suite: 923 passed (918+5), isti pre-postojeći 3 fail/1 error nepovezani
- `py_compile` čist na svim izmijenjenim/novim fajlovima
- `gitnexus_detect_changes`: risk MEDIUM, oba pogođena procesa očekivana (DB_PATH → _get_conn)

## Pronađeni problemi
- `tariff_tree_service.py`'s DB_PATH bug je bio AKTIVAN u dev modu (ne samo frozen build) —
  gori nego prvobitno pretpostavljeno, ali maskiran jer sve pozivajuće funkcije (`get_node`,
  `get_children`, `get_tree`) hvataju exception i tiho vraćaju None/prazno — vjerovatno
  je "pretraži tarifu hijerarhijski" u agent chatu oduvijek tiho ne radilo, bez ijedne
  vidljive greške korisniku ili u testovima (nema postojećih testova za ovu funkciju prije
  ovog rada).
- Prvi pokušaj AST skeniranja je greškom obuhvatio zaostali `dist/DeklarantPro/_internal/
  torch/...` PyInstaller build folder (stotine lažno-pozitivnih `@overload` funkcija) —
  ispravljeno scoping-om na projektne foldere.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
|---|---|
| 577a3b7 | fix(db-path): još dva `__file__`-relativna DB_PATH buga (ista klasa kao tarifa_2026) |
| 004b67f | perf(baza): pg_trgm indeksi za još 3 tabele bez indeksa na ILIKE upitima |
| (slijedi) | docs: dokumentuj sistematsko skeniranje iste klase bugova |

## Rizici / ograničenja
- AST skener otkriva samo doslovno duplirana IMENA metoda/funkcija — ne otkriva slične ali
  ne-identične duplikacije (npr. dvije funkcije sa različitim imenima ali istom logikom).
- Nisam provjerio SVE ILIKE pozive u `gui/` (samo `services/`) — moguće da postoje i
  direktni SQL upiti u GUI kodu van servisnog sloja (manje vjerovatno po 3-layer
  konvenciji projekta, ali nije eksplicitno provjereno).

## Potreban follow-up
- `database/migrations/008-010` nedostaju u `dist_client/database/migrations/` — pre-postojeći
  gap otkriven usput, nije popravljen (van scope-a ove sesije, ali vrijedi zabilježiti).
- Razmisliti o čišćenju zaostalog `dist/DeklarantPro/` build foldera (stari PyInstaller
  izlaz, ometao je AST sken) — nisam ga dirao bez eksplicitnog pitanja korisniku.
- Rebuild `.exe` i provjera uživo da agent chat "pretraži tarifu hijerarhijski" i
  "analiziraj tarifne historiju" sad rade ispravno.

## Potrebna korisnička potvrda
- Potvrda nakon sljedećeg rebuild-a da agent chat funkcije hijerarhijske pretrage i
  analize tarifne historije rade (ranije su bile tiho pokvarene, bez vidljive greške).
- Da li da obrišem zaostali `dist/DeklarantPro/` build folder (stari, zauzima prostor,
  ometao skeniranje) — ili ga ostaviti?
