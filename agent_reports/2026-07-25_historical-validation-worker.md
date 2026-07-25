# HistoricalValidationWorker — istorijska validacija tarifa u pozadini

## Datum
2026-07-25

## Agent
Claude (Sonnet 5)

## Scope
- `services/historical_validation_worker.py` (novo) + `dist_client/` mirror
- `gui/tabs/faktura_view.py` + `dist_client/` mirror
- `gui/main_window.py` + `dist_client/` mirror
- `tests/unit/test_historical_validation_worker.py` (novo)
- `tests/unit/test_faktura_view_provjeri_selekcija.py` (ažuriran)
- `docs/CONTEXT.md` (§59)

## Status izvora
Ovaj rad direktno adresira **nalaz 2b** iz dva nezavisna izvora koja su se
podudarila:
- `agent_reports/2026-07-25_istraga-naimenovanja-faktura-tok.md` (Pi
  istraga) — "Fajl:Linija: gui/tabs/faktura_view.py:4622... nema QThread"
- `Downloads/Codex-analiza-faktura-taba.docx` (Codex analiza, sekcija
  "Performanse") — isti bug, ista lokacija

Pi je u `agent_reports/2026-07-25_popravke-naimenovanja-faktura.md`
eksplicitno ostavio ovaj nalaz otvoren ("Srednji rizik — zahtijeva novi
QThread worker + testiranje sa stvarnim DB") i preporučio ga kao sljedeći
korak — ovaj zadatak je taj sljedeći korak, urađen nakon korisničke potvrde
(AskUserQuestion, izabrao "Implementiraj 2b" nad alternativom 3a
NaimenovanjaController, koji je ostao deferovan kao "najveći refaktor").

## GitNexus impact
- `_run_historical_tariff_validation` (upstream): MEDIUM risk, 6 impactedCount,
  5 direktnih pozivalaca (`_process_batch_records`, `_process_batch_records_
  legacy`, `_on_import_finished`, `_on_import_finished_legacy`,
  `_on_validate_all`) — svih 5 provjereno, nijedan ne koristi povratnu
  vrijednost (uvijek `None`), pa promjena signature ponašanja (sync→async)
  ne lomi nijedan pozivni ugovor.
- `NaimenovanjaView` (za poređenje, alternativa 3a): LOW po broju eksternih
  importera (2), ali VISOK po unutrašnjoj kompleksnosti (3681 linija,
  "najveći refaktor" po Pi-jevoj sopstvenoj ocjeni) — GitNexus class-import
  metrika ovdje potcjenjuje stvarni rizik, zato je 3a deferovan u korist 2b.
- `detect_changes(scope=all)` PRIJE commita: 46 promijenjenih simbola, 5
  fajlova, **0 affected_processes, risk_level LOW**.

## Šta je urađeno
1. Novi `HistoricalValidationWorker(QThread)` (`services/historical_
   validation_worker.py`) — isti `cancel()`/`_cancelled` obrazac kao
   `ProcessingWorker`/`TariffLLMWorker` (projektna konvencija). Konstruiše
   PRIVATNU `HistoricalTariffSearchService()` instancu u `run()` (ne
   singleton), poziva `validate_lines()` (DB upit), emituje `finished_
   validation(matches, auto_applied, auto_rejected)`.
2. `_run_historical_tariff_validation` podijeljen na dispatch (glavni
   thread, priprema target_lines/selekciju — logika NEIZMIJENJENA) i
   `_on_historical_validation_finished` (novi slot na glavnom threadu —
   logika remapiranja indeksa/upisa u tabelu/dijaloga SADRŽAJNO
   NEIZMIJENJENA, samo premještena).
3. Staleness guard: `_historical_validation_token` (inkrementiše se pri
   svakom dispatchu, odbacuje rezultat starijeg workera superseded novijim
   pozivom) + `_validation_generation` (postojeći brojač iz `_load_data_
   from_draft`, odbacuje rezultat ako je draft reload-ovan dok je worker
   radio). Kod mismatch-a bilo kojeg — rezultat se POTPUNO odbacuje, bez
   pokušaja remapiranja.
4. `MainWindow._shutdown_agent_workers` proširen (`_shutdown_worker()`
   izdvojen kao static helper) da gasi i ovaj worker uz Agent tab worker —
   isti cancel+quit+wait(3s)+terminate obrazac kao `eac0b3d`.

## Zašto je urađeno
Korisnik je eksplicitno odabrao ovaj nalaz (2b) nad alternativom (3a
NaimenovanjaController ekstrakcija) nakon što sam predstavio oba sa GitNexus
impact procjenom — 2b je kontejnovan (MEDIUM rizik, jedna metoda + 5 poziva
unutar istog fajla), 3a zahtijeva karakterizacione testove i zaseban
`project_rooms/` plan prije bilo kakve izmjene (van scope-a ove sesije).

## Kako je urađeno
- Pročitan `ProcessingWorker` (postojeći QThread obrazac u istom projektu)
  i `TariffLLMWorker` (iz `eac0b3d`, najnoviji `cancel()` presedan) prije
  pisanja novog workera — nova klasa slijedi identičnu strukturu
  (Signal-ovi, `_cancelled` flag, privatna instanca servisa).
- Provjereno da `validate_lines()` vraća `List[TariffHistoryMatch]`
  (dataclass, sigurno za prenos preko Qt signala kao `object`/`list` —
  isti mehanizam koji već koriste `ProcessingWorker.file_completed` i
  `TariffLLMWorker.proposals_ready`).
- Provjereno (grep) da SVIH 5 poziva `_run_historical_tariff_validation`
  ignorišu povratnu vrijednost — bezbjedno mijenjati sync→async bez
  ažuriranja pozivalaca.
- Provjereno da `_validation_generation` (postojeći brojač) biva
  inkrementiran na SVAKOM putu koji mijenja `draft.invoice_lines` indekse
  (`_on_delete_item`, `_on_clear_all`, `_on_import_finished` — svi zovu
  `_load_data_from_draft()`), osim `_on_add_item` (append-only, ne mijenja
  postojeće indekse — bezopasno da ne inkrementiše).
- `MainWindow._shutdown_worker` testiran preko duck-typed fake objekta
  (isti obrazac kao postojeći `test_main_window_exit_button.py`) — ne
  zahtijeva pravu Qt aplikaciju/MainWindow inicijalizaciju.

## Šta nije dirano
- Sadržaj logike remapiranja indeksa, upisa u tabelu, dijaloga i notifikacija
  (`_notify_auto_applied_tariffs`, `_notify_auto_rejected_tariffs`,
  `TariffValidationDialog`) — premješten bez izmjene ponašanja.
- `HistoricalTariffSearchService.validate_lines()` sama — DB upit logika
  nedirana, samo mjesto izvršavanja (thread) promijenjeno.
- `_confirm_safe_to_exit()` — namjerno NIJE proširen da blokira izlaz zbog
  historical validation workera (za razliku od Agent worker provjere) — ovaj
  posao je nizak-rizik (prijedlog za tarifu, ne gubitak korisničkog rada),
  pa dodatni blocking dijalog pri izlasku nije opravdan.
- 3a (NaimenovanjaController), 5a (`_on_import_xml` na UI threadu), 4a
  (legacy metode) — eksplicitno deferovano, van scope-a ovog zadatka.

## Verifikacija
- `python -m py_compile` na svim izmijenjenim/novim fajlovima (root +
  dist_client) — OK.
- Novi `tests/unit/test_historical_validation_worker.py` (6 testova):
  worker emituje `finished_validation` sa tačnim payload-om
  (`qtbot.waitSignal`), emituje `error_occurred` na izuzetak,
  `cancel()` prije `start()` sprječava `validate_lines()` poziv, staleness
  guard (token/generation mismatch) ne dira tabelu/draft/dijalog,
  `_shutdown_agent_workers` gasi OBA workera (Agent + Faktura).
- Ažuriran `tests/unit/test_faktura_view_provjeri_selekcija.py` (11
  testova, od toga 1 nov: prazan draft ne pokreće worker) — dispatch-testovi
  patchuju `HistoricalValidationWorker.start()` na no-op (bez pravog
  thread-a, race-free), `_on_historical_validation_finished` testovi
  pozivaju metodu direktno (bez čekanja na signal) — ista pokrivenost kao
  prije (remapiranje auto_applied/auto_rejected/match.line_index, poruke,
  auto mod), bez flaky QThread timing-a u testovima.
- Pun test suite (`python -m pytest tests/ -q`): 1135 passed (bilo 1128
  prije ovog zadatka, +7 novih), isti pre-postojeći 1 fail/1 error
  (nepovezani — hardkodovana lična putanja, nedostajuća pytest fixture).
- `gitnexus_detect_changes(scope=all)`: risk_level LOW, 0 affected_processes.
- Root vs dist_client diff nakon mirroringa: `diff -u` prazan (bit-identični)
  za sva tri izmijenjena fajla.

## Pronađeni problemi
Nema novih — implementacija je tekla prema planu bez iznenađenja.

## Konflikti / kontradiktorni izvori
Nema — Pi-jev izvještaj i Codex analiza su se SLOŽILI na istom nalazu
(različita imena, ista lokacija/uzrok), obrnuto potvrđujući nalaz umjesto
kontradikcije.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `b9594fb` | perf(faktura): premjesti istorijsku validaciju tarifa u pozadinski thread |

## Rizici / ograničenja
- `cancel()` je best-effort — ne prekida DB upit koji je već u toku (isti
  ograničenje kao postojeći `TariffLLMWorker.cancel()`, koji provjerava
  cancellation samo između batch-eva, ne usred jednog API poziva). Za ovaj
  worker, "usred jednog poziva" znači usred `validate_lines()` — nema
  finije granularnosti bez izmjene same `HistoricalTariffSearchService` da
  prima cancel-check callback (van scope-a, veća invazivnost).
- Ako korisnik brzo klikne "Provjeri" više puta uzastopno, prethodni workeri
  nastavljaju raditi u pozadini (DB upit se ne prekida), samo im se rezultat
  odbacuje — moguće privremeno gomilanje DB konekcija pri vrlo brzom
  ponovljenom klikanju (rijedak scenario, nije mjereno/testirano pod
  stvarnim opterećenjem).

## Potreban follow-up
- Preostali Pi/Codex nalazi (3a NaimenovanjaController, 5a `_on_import_xml`
  worker, 4a legacy metode) — kandidati za buduće, zasebne sesije.
- Ako se pokaže da brzi uzastopni klik na "Provjeri" pravi mjerljiv problem
  (gomilanje DB konekcija), razmotriti debounce na dugmetu ili
  connection-pool limit.

## Potrebna korisnička potvrda
- Nema — implementacija je direktno izvršenje korisnikom odobrenog plana
  (AskUserQuestion odgovor "Implementiraj 2b").
