## Datum
2026-07-25

## Agent
Claude Code (Sonnet 5, kasnije Opus 5)

## Scope
- Pregled git istorije/agent_reports rada Codex+Pi agenata (114 commitova,
  307 fajlova, redizajn + jedinstveni import workflow refaktoring)
- `.env` + `dist_client/.env` — ažuriranje DB_HOST na novu DHCP adresu
- `tests/integration/test_real_invoice_import_e2e.py` (novo)
- `services/import_service.py` + `dist_client/` kopija (fix)
- `importers/vendors/medicopharm/medicopharm_importer.py` + `dist_client/`
  kopija (fix)
- `gui/tabs/faktura_view.py` + `dist_client/` kopija (fix)
- `tests/unit/test_import_service_tariff_normalization.py` (novo)
- `tests/unit/test_medicopharm_pdf_parser.py` (dopunjen)
- `tests/unit/test_faktura_view_tariff_description_db_path.py` (novo)
- `project_rooms/2026-07-25_ukloni-lijevu-dopunu-kratkih-tarifa.md`
- Verifikacija (bez izmjene) paralelnog izvještaja drugog agenta
  (`agent_reports/2026-07-25_istraga-naimenovanja-faktura-tok.md`, Pi)

## Status izvora
Aktivni, autoritativni izvori: `agent_reports/2026-07-24_import-workflow-
zavrsne-faze-batch.md` i `agent_reports/2026-07-24_spajanje-redizajna-u-
windows.md` (najnoviji Codex izvještaji, eksplicitno traže ručnu GUI potvrdu
sa stvarnim fakturama — taj zahtjev je pokretač ovog zadatka).
`agent_reports/2026-07-25_istraga-naimenovanja-faktura-tok.md` (Pi, paralelan
rad) — TRETIRAN KAO NEPROVJEREN dok se ručno ne potvrdi svaki nalaz (isti
standard kao za sopstvene nalaze); rezultat provjere u sekciji "Konflikti"
niže.

## GitNexus impact
- `ImportService._normalize_tariffs_in_result`: **HIGH** (12 impactedCount,
  2 pogođena procesa preko `ProcessingWorker.run`/`ImportWorker.run`,
  univerzalna funkcija — svi import putevi). Plan napisan prije izmjene per
  AGENTS.md, korisnik eksplicitno potvrdio smjer odluke (AskUserQuestion)
  prije primjene.
- `medicopharm_importer.py::_try_parse_item_line`: LOW (4 impactedCount,
  izolovano na Medicopharm parser lanac).
- `FakturaView._get_tariff_description`: LOW (2 impactedCount, poziva se iz
  `_show_tariff_preview_dialog` → `_on_auto_fill`).
- `gitnexus_detect_changes(scope=all)` nakon sve tri izmjene: risk LOW-MEDIUM,
  svi pogođeni procesi/simboli odgovaraju tačno namjeravanim izmjenama.

## Šta je urađeno
1. **Pregled urađenog posla** (Codex+Pi, dok je korisnik odsustvovao): git
   log, 15+ agent_reports, potvrđeno da su svi "crveni" testovi (10 od 11
   padova) bili isključivo posljedica nedostupnog PostgreSQL servera (DHCP
   promjena IP-a), ne regresija koda.
2. **Ažuriran `.env`** (root + `dist_client/`) na novu DB IP
   `192.168.100.154`, očišćene stare zakomentarisane linije.
3. **E2E integracioni test** jedinstvenog import workflow-a sa stvarnim
   fakturama (Master Frigo, PIP Food, SRECKO, Medicopharm 1476/26) — pokriva
   4 scenarija koje su Codex-ovi izvještaji eksplicitno označili kao
   nepotvrđene (jedan uvoz, REPLACE na ponovni uvoz, konflikt partnera,
   kombinovani uvoz sa `consumed_paths`).
4. **Dva stvarna buga otkrivena i popravljena** tokom dubljeg testiranja
   Medicopharm fakture (94 stavke, per-item PE izjava, ista tarifa iz više
   zemalja):
   - `_normalize_tariffs_in_result()` fabrikovao pogrešno poglavlje za
     nepotpune 4-7-cifrene tarife (zfill lijevo umjesto ostaviti nepotpuno)
   - Medicopharm parser dozvoljavao curenje razmakom-odvojenog zemljinog
     sufiksa u naziv robe
5. **Provjeren i djelimično primijenjen** paralelan Pi izvještaj (bez
   slijepog vjerovanja) — jedan nalaz potvrđen kao zastario (već popravljen),
   drugi potvrđen kao stvaran i popravljen (§1b, `_get_tariff_description`).

## Zašto je urađeno
Korisnik je tražio moje mišljenje o velikom talasu rada urađenom sa Codex i
Pi agentima. Pregled je otkrio da je JEDINA preostala nepoznanica (po
riječima samih Codex izvještaja) ručna potvrda da jedinstveni import
workflow radi na stvarnim podacima — to je bio "blocking" rizik prije nego
se poslovna logika smatra pouzdanom. Korisnik je zatim tražio da se to
stvarno uradi, i priložio dodatnu, strukturno najzahtjevniju fakturu
(Medicopharm 1476/26) kad su prve četiri prošle bez problema. Dodatna
izmjena (§1b) je uradjena jer je paralelni Pi izvještaj sletio u istu sesiju
i sadržavao potvrdivo stvaran, iste-klase bug koji je bilo jeftino odmah
zatvoriti dok je kontekst (frozen DB_PATH obrazac) već svjež.

## Kako je urađeno
- Headless (bez GUI-ja, koji zahtijeva displej) end-to-end poziv kroz stvarni
  servisni sloj: `ImportService.import_file()` → `from_import_result()` →
  `prepare_import()` → `apply_import_plan()`, sa PE/EUR1 dijalog odgovorima
  simuliranim kao `SKIPPED`.
- Očekivane vrijednosti uzete direktno iz zbirnog sažetka svake fakture
  (broj stavki, ukupan iznos, bruto/neto težina, per-item PE raspon, tabela
  tarifa/zemalja) — "zlatni standard" jer je nezavisan od koda koji se
  testira.
- Za sva tri fixa: prvo potvrđen stvaran uzrok (direktan `pdfplumber` izvod
  sirovog teksta za Medicopharm redove; direktno čitanje koda i uživo poziv
  metode za `_get_tariff_description`), zatim GitNexus impact, zatim
  minimalna ciljana izmjena, zatim regresioni test na dva nivoa (izolovan
  jedinični + e2e/funkcionalan).
- Za `zfill` fix (HIGH impact): zaustavljen tok, korisniku eksplicitno
  postavljeno pitanje (AskUserQuestion) sa tri opcije prije primjene —
  birana preporučena opcija.
- Za `_get_tariff_description` fix: umjesto dupliranja `_resolve_db_path()`
  logike po četvrti put u istoj sesiji, ponovo iskorišten već popravljen
  `tariff_hierarchy._DB_PATH` (DRY, jedan izvor istine za putanju baze).

## Šta nije dirano
- Sama import-workflow arhitektura (`services/import_workflow/*`) — testirana,
  ne mijenjana.
- `normalize_tariff_number()` u `importers/invoice_line_utils.py` — već
  ispravno ponašanje, nije izvor buga.
- Grane za 10-cifreni i >10-cifreni tarifni kod u
  `_normalize_tariffs_in_result` — netaknute, rade ispravno.
- `declaration_validator_service.py` — sigurnosni mehanizam koji hvata
  nepotpune tarife, samo iskorišten kao dokaz da uklanjanje zfill-a ne
  ostavlja rupu.
- Ostatak Pi izvještaja (arhitekturni dug — Naimenovanja bez Controller
  sloja, N+1 upiti, QThread `cancel()`, legacy metode) — NIJE provjeravan
  niti primjenjivan, ostaje kao katalog za budući rad.
- AGENTS.md/CLAUDE.md pre-postojeće izmjene (vidljive u git status od
  početka sesije) — nisu moje, nisu dirane.

## Verifikacija
- Direktan `pdfplumber` izvod sirovog PDF teksta za oba Medicopharm reda
  prije bilo kakve izmjene.
- Uživo potvrđeno u bazi: `03304990` (fabrikovana pogrešna tarifa) NE postoji
  u `catalogs.zvanicna_tarifa` — postojeća ERROR-nivo validacija već hvata
  posljedicu bez obzira na ovaj fix.
- Nakon svih fixova: 94 stavke, iznos 22.662,72 EUR, bruto 310/neto 284,94 kg
  — identično sažetku fakture (nema regresije u ukupnim iznosima).
- Eksplicitna provjera da nijedan drugi naziv robe na fakturi ne počinje
  brojem (da fix za Medicopharm sufiks ne odsijeca legitimne nazive).
- `_get_tariff_description('33049900')` uživo vraća stvaran opis
  ("Proizvodi za uljepšavanje...") umjesto praznog stringa.
- `py_compile` čist na svim izmijenjenim/novim fajlovima (root + dist_client).
- Pun test suite (nakon sve tri izmjene): **1107 passed**, 58 skipped, 5
  xfailed, 1 fail (poznat, hardkodovana Linux putanja) + 1 error (poznat,
  nedostajući fixture) — nepovezani, isti kao prije bilo koje izmjene u ovoj
  sesiji.
- `gitnexus_detect_changes` nakon svakog commita: risk LOW/MEDIUM, svi
  pogođeni procesi odgovaraju namjeravanim izmjenama.

## Pronađeni problemi
- Prvi pokušaj e2e testa za REPLACE scenario je lažno pokazao duplikat (102
  umjesto 51 stavke) — uzrok je bio u SAMOM TESTU (koristio `invoice_name`
  umjesto `invoice_number` za građenje `existing_invoice_keys`, različito od
  stvarnog GUI koda `FakturaView._existing_invoice_keys_for_import_workflow`).
  Ispravljeno kopiranjem tačne logike iz GUI-ja.
- `_normalize_tariffs_in_result`'s zfill(8) je bio moj vlastiti kod iz ranije
  sesije (komit `ca682c4`, 2026-06-16) — namjeravan za uski slučaj (poglavlje
  01-09, izostavljena vodeća nula), ali implementiran preširoko.
- Paralelni Pi izvještaj je sadržavao jedan zastario nalaz (§1a) — generisan
  prije mog commita koji je već riješio taj problem. Potvrđuje vrijednost
  pravila "provjeri tuđi izvještaj prije djelovanja", isto kao za sopstvene
  nalaze ranije u sesiji.

## Konflikti / kontradiktorni izvori
`agent_reports/2026-07-25_istraga-naimenovanja-faktura-tok.md` (Pi, §1a)
tvrdio je da dist_client i dalje ima `zfill(8)` bug — ZASTARIO u trenutku
čitanja (moj commit `db7f05d` je već mirrovao fix u oba fajla prije nego je
taj izvještaj pročitan). Tretiran kao neaktuelan, potvrđeno diff-om uživo.
Nije potrebna korisnička potvrda — činjenično pitanje, riješeno provjerom.

## Commitovi
| Hash | Poruka |
|---|---|
| ed8f219 | test(import): e2e integracioni test workflow-a sa stvarnim fakturama |
| db7f05d | fix(import): ukloni pogresnu lijevu dopunu kratkih tarifnih brojeva |
| dd136aa | fix(medicopharm): sprijeci curenje razmakom-odvojenog zemljinog sufiksa u naziv robe |
| 89f54bb | fix(db-path): jos jedan __file__-relativni DB_PATH bug (FakturaView tarifni opis) |

## Rizici / ograničenja
- E2E test se preskače graciozno ako arhiva faktura nije dostupna (fakture
  sadrže stvarne poslovne podatke, nisu u repou) — regresija ovih tačnih
  bugova neće biti uhvaćena automatski na mašinama bez arhive.
- Nisam kliktao kroz stvarni Qt PE2/EUR1 dijalog widget — simuliran je
  odgovor korisnika programski.
- Uklanjanje zfill-a za 4-7 cifara je testirano na sintetičkim vrijednostima
  i jednom stvarnom slučaju — nije isključeno da neki DRUGI dobavljač ima
  drugačiji uzorak nepotpune tarife koji sad prolazi bez dopune (očekivano
  i ispravno po novoj politici, ali vrijedi pratiti).
- Ostatak Pi izvještaja (arhitekturni dug) nije provjeravan — sadržani
  nalazi mogu biti tačni ili zastarjeli, nepoznato dok se ne provjeri isto
  rigorozno kao §1a/§1b.

## Potreban follow-up
- Ostala 4 scenarija koja su Codex izvještaji tražili za ručnu GUI potvrdu
  (grupni uvoz više faktura, batch sa PE2/EUR1 dijalogom kroz stvarni UI)
  — headless testiranje ih ne pokriva u potpunosti.
- Ako se korisnik odluči baviti arhitekturnim dugom iz Pi izvještaja
  (Naimenovanja Controller sloj, N+1 upiti, QThread cancel()), svaki nalaz
  treba provjeriti prije primjene istim standardom kao ovdje (§1a je bio
  zastario, §1b stvaran — omjer sugeriše da ni ostatak ne treba uzeti zdravo
  za gotovo).
- Razmisliti o periodičnom ponavljanju e2e provjere sa NOVIM stvarnim
  fakturama.

## Potrebna korisnička potvrda
- Ručno kroz GUI potvrditi PE2/EUR1 dijalog widget interakciju.
- Potvrditi da su ova tri fixa dovoljna — ako se pojave DRUGE fakture sa
  sličnim "ružnim" formatiranjem, prijaviti za dodatnu istragu.
