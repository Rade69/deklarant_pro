# DB grešku ne miješati sa "nema istorijskog prijedloga"

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `services/agent/validation/historical_tariff_search_service.py` + `dist_client/` mirror
- `services/historical_validation_worker.py` + `dist_client/` mirror
- `gui/tabs/faktura_view.py` + `dist_client/` mirror (`_on_historical_validation_error`)
- `.env` / `dist_client/.env` (DB_HOST ažuriran, van gita)
- Sistemski: OCR (pytesseract + Tesseract 5.4.0 preko winget)
- 2 test fajla (9 novih/proširenih testova)
- `docs/CONTEXT.md` (§64)

## Status izvora
Live debug sesija — korisnik pokrenuo aplikaciju (na moj zahtjev/akciju),
prijavio konkretan simptom uz screenshot-e i podatke (faktura 1476/26,
stavka "SUSSINA 650 tbl.", tarifa 38249993, poruka "nema boljeg
istorijskog prijedloga"). Istraga urađena uživo, direktnim upitima na
bazu i pozivima servisa, ne iz postojeće dokumentacije.

## GitNexus impact
- `validate_lines` (upstream): **HIGH**, impactedCount 22, 6 direktnih
  pozivalaca (`HistoricalValidationWorker.run`, Agent chat tool
  `_prikaz_tarifnih_trenutnih` preko `_dispatch_known_tool`/
  `_handle_message_regex_fallback`, `scripts/agent_tariff_eval_report.py`
  preko `evaluate_case`).
- Odlučeno: dizajn fix-a je namjerno **aditivan** — `_search_one()`/
  `validate_lines()` zadržavaju IDENTIČAN povratni tip i ponašanje za sve
  postojeće pozivaoce (novi `self.last_db_error` atribut se postavlja ali
  ništa ga ne MORA čitati; stari pozivaoci rade nepromijenjeno). Ovo drži
  stvaran rizik nizak uprkos HIGH GitNexus ocjeni na osnovnu metodu —
  nijedan od 6 direktnih pozivalaca nije morao biti izmijenjen niti
  testiran zbog ovog fix-a.
- `detect_changes(scope=staged)` prije commita: risk LOW, 0 affected —
  potvrđuje procjenu.

## Šta je urađeno

### Dijagnoza (redoslijed koraka)
1. Aplikacija pokrenuta (`python run.py`, background) — log pokazao
   "OCR nedostupan" (WARNING) i "PostgreSQL server 192.168.100.154 timeout"
   (ERROR, session_manager).
2. Korisnik prijavio "SUSSINA" problem uz screenshot: selektovana stavka,
   "Provjeri" → "nema boljeg istorijskog prijedloga od trenutno unesenog
   tarifnog broja".
3. Korisnik javio: server sada na `192.168.0.25`, treba instalirati
   `pytesseract`.
4. `.env`/`dist_client/.env` ažurirani na novi IP, DB konekcija verifikovana.
5. `pytesseract`/`pdf2image`/`opencv-python` instalirani preko pip (na isti
   interpreter koji pokreće app — `uv` nije bio na PATH-u u ovoj shell
   sesiji). Tesseract binarni fajl NIJE bio prisutan sistemski — instaliran
   preko `winget install --id UB-Mannheim.TesseractOCR`. Potvrđeno:
   `importers/pdf/ocr_utils.py::_find_tesseract()` VEĆ auto-detektuje
   standardnu winget install lokaciju (`C:\Program Files\Tesseract-OCR\
   tesseract.exe`) — nije bila potrebna nikakva PATH izmjena niti izmjena
   koda.
6. Aplikacija ponovo pokrenuta — čist startup log (bez OCR/DB grešaka).
7. Direktan upit na `catalogs.product_tariff_mapping` (`naziv_robe ILIKE
   '%SUSSINA%'`) — pronađeno 15 istorijskih zapisa, svi mapiraju na
   `21069098`, dobavljač MEDIKO, usage_count 1-43.
8. Direktan poziv `HistoricalTariffSearchService.validate_lines()` sa
   linijom identičnom fakturi (naziv "SUSSINA 650 tbl.", tarifa 38249993,
   izvoznik MEDIKOPHARM) — vratio **0 prijedloga**, ALI `last_auto_applied`
   je sadržavao `[(0, '21069098')]` — znači sistem je NAŠAO jak dokaz i
   auto-primijenio bi ga (ranija "accept" povratna informacija), ne
   "nema prijedloga".
9. Rekonstruisano: kad je korisnik kliknuo "Provjeri", DB je bio
   NEDOSTUPAN — `_search_one()` je tiho uhvatio izuzetak i vratio `[]`,
   pa je CIJELA provjera izgledala kao "provjereno, nema prijedloga"
   umjesto "nije provjereno".

### Fix
- `HistoricalTariffSearchService.__init__`: novi `self.last_db_error:
  str | None = None`.
- `validate_lines()`: resetuje `self.last_db_error = None` na početku
  (uz postojeći reset `last_auto_applied`/`last_auto_rejected`).
- `_search_one()`: dodat `except psycopg2.Error as e:` PRIJE generičkog
  `except Exception:` — postavlja `self.last_db_error = str(e)`, loguje,
  vraća `[]` (isto kao prije za sam povratni tip). Generički (ne-DB)
  izuzeci i dalje se tiho gutaju bez `last_db_error` — nepromijenjeno.
- `HistoricalValidationWorker.run()`: nakon `validate_lines()`, provjerava
  `svc.last_db_error` — ako postavljen, emituje `error_occurred(poruka)`
  UMJESTO `finished_validation([], [], [])`.
- `FakturaView._on_historical_validation_error(self, message, auto=False)`:
  novi `auto` parametar (threaded kroz lambda na `worker.error_occurred.
  connect(...)`), prikazuje `QMessageBox.warning` kad `not auto` — ranije
  je SAMO logovao (korisnik nije vidio ništa čak ni na stvarnu grešku).

## Zašto je urađeno
Korisnik je eksplicitno potvrdio (AskUserQuestion) da želi fix nakon što
sam objasnio dijagnozu. Problem je bitan jer korisnik direktno donosi
poslovne odluke (da li mijenjati tarifni broj) na osnovu ove poruke —
"nema prijedloga" kad je zapravo "nismo mogli provjeriti" je opasno
zavaravajuće u carinskom kontekstu.

## Kako je urađeno
- Prije bilo kakve izmjene, dijagnoza je urađena UŽIVO direktnim pozivima
  na stvarnu bazu i servis (ne pretpostavkama) — svaki korak u dijagnozi
  gore je stvarno izvršen i njegov rezultat zabilježen prije zaključka.
- Provjerena tačna hijerarhija izuzetaka (`psycopg2.pool.PoolError` i
  `psycopg2.OperationalError` obje nasljeđuju `psycopg2.Error`) prije
  pisanja `except` klauzule, da se osigura da HVATA oba realna scenarija
  (circuit breaker I direktan connection timeout).
- GitNexus impact provjeren PRIJE izmjene; pošto je HIGH, eksplicitno
  razmotren dizajn koji minimizira stvaran rizik (aditivan atribut umjesto
  promjene povratnog tipa/signature) — ovo je bila SVJESNA arhitektonska
  odluka da se izbjegne dodirivanje 6 direktnih pozivalaca.
- Svaki test sloj (servis, worker, UI handler) testiran odvojeno prije
  integracije, matching postojeći test-file organizacija u projektu.

## Šta nije dirano
- Agent chat tool (`_prikaz_tarifnih_trenutnih` i lanac poziva) — ne provjerava
  `last_db_error`, ponaša se identično kao prije (tiha degradacija na
  prazan rezultat unutar chat konteksta — prihvatljivo, chat je manje
  kritičan tok od Faktura tab "Provjeri" dugmeta).
- `scripts/agent_tariff_eval_report.py` — offline eval skripta, ne
  provjerava `last_db_error`, nepromijenjeno ponašanje.
- Generički (ne-`psycopg2.Error`) izuzeci u `_search_one()` — i dalje se
  tiho gutaju, nepromijenjeno.
- `_query_strict`/`_query_broad`/SQL logika — netaknuto, ovo NIJE bio
  bug u samoj logici pretrage (ona je radila ispravno kad je DB dostupna).

## Verifikacija
- `python -m py_compile` na sva tri izmijenjena fajla (root + dist_client).
- 9 novih/proširenih testova: DB-error postavljanje i reset (servis),
  worker error-routing kad je last_db_error postavljen, UI dialog
  auto/ne-auto ponašanje.
- Pun test suite: **1174 passed** (bilo 1156 prije ovog fix-a — razlika
  uključuje i to da su DB-backed testovi iz `test_decision_
  characterization.py` sada PROŠLI jer je server dostupan, ne samo novi
  testovi). Isti 1 pre-postojeći nepovezan fail (hardkodovana lična
  putanja).
- `gitnexus_detect_changes(scope=staged)`: risk LOW, 0 affected.
- Root vs dist_client diff nakon mirroringa: identičan sadržaj.
- Uživo potvrđeno (direktan poziv, ne test mock): `validate_lines()` sa
  dostupnom bazom sad vraća ispravan rezultat za SUSSINA slučaj.

## Pronađeni problemi
Nema dodatnih van onoga što je opisano — ovo JE nalaz i fix u jednom.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `db3ca95` | fix(tariff): razlikuj 'DB nedostupna' od 'nema istorijskog prijedloga' |

## Rizici / ograničenja
- Ako DB padne NAKON što je prva stavka uspješno provjerena (djelimičan
  failure usred `validate_lines()` petlje kroz više linija), trenutni
  dizajn i dalje postavlja `last_db_error` (posljednja neuspješna linija
  pobjeđuje) i CIJELA provjera se tretira kao neuspjela u
  `HistoricalValidationWorker`, čak i ako su neke linije uspješno
  provjerene prije pada. Ovo je namjerno konzervativno (sigurnije nego
  djelimično primijeniti nepotpune rezultate), ali znači da jedan
  tranzijentan hiccup usred velike fakture odbacuje SVE, ne samo
  pogođenu liniju.
- Agent chat tok (`_prikaz_tarifnih_trenutnih`) NE prikazuje korisniku
  da provjera nije uspjela — samo Faktura tab "Provjeri" dugme je
  pokriveno ovim fix-om.

## Potreban follow-up
Nema hitnog — otvoreno je da se Agent chat tok kasnije uskladi sa istim
principom ako se pokaže potrebnim (nije prijavljen kao problem).

## Potrebna korisnička potvrda
- Da potvrdi da je SUSSINA stavka sada ispravno prepoznata/ažurirana u
  aplikaciji nakon ponovnog pokretanja (ja sam potvrdio direktnim pozivom
  servisa, ali ne i kroz stvaran GUI klik).
