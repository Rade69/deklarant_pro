# Dovršetak paketa stabilnosti i dijagnostike

## Datum

2026-07-24

## Agent

Codex

## Scope

- Qt bulk popunjavanje u Šifrarnicima, root i `dist_client`
- frozen putanje za dvije lokalne SQLite baze
- logovanje prethodno prećutanih grešaka u XML i tarifnom evidence toku
- uklanjanje produkcionih `print()` poziva iz `AgentTab`
- regresioni testovi za stanje Qt tabela i frozen DB putanje

## Status izvora

- `agent_reports/2026-07-23_samostalna-istraga-tehnicki-dug.md`: aktivan izvor nalaza
- `project_rooms/2026-07-23_evidence-adapters-logging-fix.md`: aktivan CRITICAL plan
- raniji pokušaj izmjene `MainWindow._confirm_safe_to_exit`: povučen i nije dio izmjene
- drift `faktura_view.py`: treba korisničku potvrdu i nije diran

## GitNexus impact

`adapt_tariff_evidence` je CRITICAL: centralni tarifni evidence tok učestvuje u
odlučivanju, prikazu, agent auto-popuni i sinhronizaciji nacrta. Izmjena je ograničena
na `logger.warning`; kontrolni tok i povratna vrijednost ostali su isti.

`SifarniciView._populate_table_from_service` je MEDIUM (18 pogođenih simbola, 11
direktnih poziva). `populate_tariff_hierarchy`, `QuotaPanel._populate_table`, DB putanje
i dvije metode `AgentTab` imaju LOW rizik.

Završni `detect_changes` označio je paket kao CRITICAL isključivo zbog prisustva
`adapt_tariff_evidence`; pogođeni procesi odgovaraju unaprijed prijavljenom planu.

## Šta je urađeno

- Tri bulk-populate toka sada blokiraju signale bezbjedno i vraćaju prethodna Qt stanja
  u `finally` bloku.
- `llm_audit.db` i `deklarant_sistem.db` u frozen režimu koriste bazu pored `.exe`.
- XML xpath i tarifni mapping izuzeci više ne nestaju bez log zapisa.
- Produkcioni Agent tab koristi logger umjesto konzolnog `print()` ispisa.
- Root i odgovarajuće `dist_client` Python kopije su usklađene.

## Zašto je urađeno

Prethodne bulk izmjene mogle su ostaviti tabelu bez signala ili osvježavanja ako
formatiranje jednog reda baci izuzetak. Započeti frozen resolver je mogao pogrešno
izabrati `_internal/database` samo zato što direktorij postoji. Prećutani izuzeci su
otežavali dijagnostiku bez ikakve koristi za korisnika.

## Kako je urađeno

Sačuvana su prethodna Qt stanja i vraćena u `finally`. Frozen resolver odmah vraća
putanju izvedenu iz `sys.executable`, dok razvojni režim zadržava postojeće kandidate.
Logging izmjene ne mijenjaju postojeće fallback ponašanje.

## Šta nije dirano

- `gui/main_window.py` i lifecycle `ProcessingWorker`
- `gui/tabs/faktura_view.py` i njegov `dist_client` drift
- tarifni pragovi, evidence score i odluke
- nepovezane izmjene u `AGENTS.md`, `CLAUDE.md` i lokalni build artefakti
- preostali Pi nalazi o velikim klasama, shimovima, scripts arhivi i MCP alatima

## Verifikacija

- ciljani paket: 27/27 testova prolazi
- novi regresioni testovi: 5/5 prolazi
- `py_compile`: svi izmijenjeni Python fajlovi prolaze
- root/dist mirror provjera: bez razlika za zajedničke izmijenjene fajlove
- puni paket: 928 passed, 58 skipped, 5 xfailed; 3 fail + 1 error su postojeći
  infrastrukturni problemi van scope-a

## Pronađeni problemi

Puni pytest trenutno uključuje benchmark funkciju bez fixture-a, skenira generisani
`dist/torch`, čita jedan fajl pod Windows podrazumijevanim `cp1252` dekoderom i ima XML
test sa hardkodovanom Linux putanjom.

## Konflikti / kontradiktorni izvori

Početni resolver kandidata sugerisao je provjeru razvojne `__file__` putanje prije
frozen exe putanje. Važeći izvor je runtime arhitektura iz `docs/CONTEXT.md`: read-write
baza živi pored `.exe`, pa frozen putanja mora imati prioritet. Korisnička potvrda nije
potrebna jer je to popravka potvrđenog deployment invariant-a.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `96e1689` | `fix(stabilnost): dovrsi zastitu tabela i dijagnostiku` |

## Rizici / ograničenja

`dist_client/services/tariff_doc_history_service.py` ne postoji kao Python izvor; tamo
je prisutan kompajlirani modul. Root popravka će ući u `dist_client` tek kroz naredni
build, pa ručno kopiranje `.py` fajla nije rađeno.

## Potreban follow-up

Sljedeće treba zasebno provjeriti: preostale emoji `print()` pozive, zastarjelu
konfiguracionu dokumentaciju, pogrešno smještene izvještaje i backup CSV fajlove,
`constants.py.__all__`, shim importe i odnos MCP/ugrađenih agent alata.

## Potrebna korisnička potvrda

Pri prvom narednom Windows buildu provjeriti da se LLM audit i historija tarifnih
dokumenata upisuju u bazu pored `.exe`.
