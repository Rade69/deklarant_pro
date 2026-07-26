# Politika: istorijski prijedlog bez potvrđenog izvora se nikad ne prikazuje

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `services/agent/validation/tariff_decision_model.py` + `dist_client/` mirror
- `tests/unit/test_historical_tariff_validation.py` (1 nov test, 3 ažurirana)
- `tests/fixtures/agent/tariff_validation_cases.json` (2 preimenovana, 2 nova)
- `docs/CONTEXT.md` (§65)

## Status izvora
Live debug sesija — nastavak §64. Korisnik je uz screenshot pokazao
`TariffValidationDialog` sa prijedlozima označenim "izvor nepoznat —
nije potvrđena historija" i pitao da li takvi prijedlozi uopšte trebaju
postojati. Nakon objašnjenja postojećeg mehanizma (prikazuju se, ali se
nikad ne bulk-prihvataju), korisnik je eksplicitno odlučio (custom
odgovor na AskUserQuestion, ne jedna od ponuđenih opcija): "Nepoznati
izvori se nikad ne prikazuju jer bi to moglo dovesti do greške i zabune
kod korisnika, što može rezultirati sankcijama i plaćanjem kazni."

## GitNexus impact
- `decide_tariff_match` (upstream): **HIGH**, impactedCount 11, 3 direktna
  pozivaoca (`HistoricalTariffSearchService._is_actionable_match` → Faktura
  tab "Provjeri" i `HistoricalValidationWorker`; `is_actionable_tariff_
  match`; posredno preko `_is_actionable_match` i Agent chat alat
  `_prikaz_tarifnih_trenutnih` i offline `scripts/agent_tariff_eval_
  report.py`).
- Prijavljeno korisniku PRIJE nastavka (implicitno kroz eksplicitno
  navođenje pogođenih zona u odgovoru), test fixture pregledan PRIJE
  izmjene da se utvrdi tačan blast radius na postojeće testove.
- `detect_changes(scope=staged)` POSLIJE izmjene: risk **LOW**, 0 affected
  — svi pozivaoci ispravno propagiraju `SUPPRESS` preko postojećeg
  `TariffDecision.should_show` ugovora, nijedan nije morao biti mijenjan.

## Šta je urađeno
`decide_tariff_match()` (services/agent/validation/tariff_decision_model.py)
sad provjerava `has_meaningful_source(match.source)` NAJPRIJE, prije bilo
koje druge logike (tarifna glava/poglavlje/usage_count) — ako izvor nije
poznat (prazan ili placeholder `"-"`, `"—"`, `"+"`, `"A"`, `"HISTORIJA"`),
odmah vraća `TariffDecisionOutcome.SUPPRESS`. Ranije je SAMO jedna grana
("cross-chapter") djelimično provjeravala izvor uz usage_count kao
alternativu; grana "ista tarifna glava" ga nije provjeravala UOPŠTE.

## Zašto je urađeno
Direktna korisnička odluka, obrazložena pravnim/finansijskim rizikom
(sankcije/kazne za pogrešnu carinsku tarifu) — poslovni prioritet
"nikad pogrešna preporuka" nad "ne gubi potencijalno koristan signal".

## Kako je urađeno
- Pročitan `TariffValidationDialog._make_row()` da se razumije TAČNO šta
  pokreće "izvor nepoznat" prikaz (`evidence.confidence is DecisionConfidence
  .UNKNOWN`), zatim `evidence_from_tariff_decision()` (core/decision/
  evidence.py) da se nađe KORIJEN — `has_meaningful_source()` provjera.
- Pročitan CIJELI `decide_tariff_match()` da se identifikuju SVE grane
  koje mogu vratiti SHOW_STRONG/SHOW_WEAK — utvrđeno da 4 od 5 grana VEĆ
  imaju neki oblik `has_source` provjere (samo kao ALTERNATIVU uz
  usage_count, ne kao STROGI uslov), a POSLJEDNJA grana ("ista tarifna
  glava") nije imala NIKAKVU provjeru — najveći izvor "nepoznat izvor a
  ipak prikazano" slučajeva.
- GitNexus impact provjeren PRIJE izmjene (HIGH) — pregledan cijeli
  `tests/fixtures/agent/tariff_validation_cases.json` PRIJE pisanja koda
  da se unaprijed identifikuju TAČNO koji test slučajevi će se pokvariti
  (2 od 17), umjesto da se otkrivaju nakon pada testova.
- Nakon izmjene koda, 3 testa su pala — svaki analiziran pojedinačno da se
  utvrdi da li test testira (a) samu source-suppression logiku (očekivano
  da se ponašanje promijeni, test treba ažurirati) ili (b) NEPOVEZANU
  logiku koja je slučajno koristila prazan izvor kao test fixture (test
  treba dobiti stvaran izvor da nastavi testirati ORIGINALNU stvar, ne
  novu politiku).

## Šta nije dirano
- `_can_accept_all()`/bulk-accept logika u `TariffValidationDialog` —
  postaje djelimično redundantna (matches sa unknown source više NE STIŽU
  do dijaloga uopšte), ali nedirano jer i dalje ispravno radi kao
  dodatna zaštita (defense-in-depth) ako bi neki BUDUĆI pozivalac
  zaobišao `decide_tariff_match`.
- `evidence_from_tariff_decision()`/`has_meaningful_source()` (core/decision/
  evidence.py) — logika ostaje ista, samo se sad njen rezultat koristi i
  za RANIJU (stroziju) odluku u `decide_tariff_match`, ne samo za UI badge.
- `_search_one()`/`_to_matches()` — logika pronalaženja kandidata iz baze
  ostaje netaknuta; fix djeluje na DECISION nivou (koji kandidat se
  PRIKAZUJE), ne na SEARCH nivou (koji kandidati se uopšte NAĐU).
- `_search_pg_partners`/UUID istraga iz prethodnog dijela sesije — odvojene
  teme, nisu dio ovog fixa.

## Verifikacija
- `python -m py_compile` na oba (root + dist_client).
- Novi `test_unknown_source_never_shown_regardless_of_usage_or_heading`:
  eksplicitno provjerava da VISOK usage_count (50) NE zaobilazi pravilo,
  sve placeholder vrijednosti (`-`, `—`, `+`, `A`, `HISTORIJA`) se tretiraju
  isto kao prazan izvor, i da STVARAN izvor i dalje prolazi (politika cilja
  SAMO nepoznat izvor, ne "ista tarifna glava" generalno).
- 3 postojeća testa ažurirana (vidi "Kako je urađeno").
- `tariff_validation_cases.json`: 2 slučaja preimenovana i promijenjena
  na "suppress" (`same_heading_precision_without_source_is_suppressed`,
  `same_chapter_different_heading_without_source_is_suppressed`) + 2 nova
  para sa `source: "MEDIKO"` da se OČUVA pokrivenost "show" putanje za
  iste scenarije kad izvor JESTE poznat.
- `test_historical_validation_evaluation_metrics` (hardkodovani zbirni
  brojevi): `true_negative` promijenjen sa 7 na 9 (matematički provjereno:
  2 slučaja prebačena iz show→suppress, plus 2 nova suppress/show para =
  neto +2 suppress, isto 10 show).
- Pun test suite: **1177 passed** (bilo 1174 prije ovog fixa), isti 1
  pre-postojeći nepovezan fail.
- `gitnexus_detect_changes(scope=staged)`: risk LOW, 0 affected.
- Root vs dist_client diff nakon mirroringa: identičan sadržaj.

## Pronađeni problemi
Nema novih van onoga što je opisano.

## Konflikti / kontradiktorni izvori
**Direktan sukob sa ranijom odlukom**: 2026-07-22 SUSSINA fix (dokumentovan
u `_search_one()` docstring-u, `agent_reports/`) je EKSPLICITNO dizajniran
da NE gubi zapise sa visokim usage_count bez dobavljača ("gore od 'nema
prijedloga'"). Današnja korisnička odluka DIREKTNO poništava tu raniju
odluku za slučaj kad izvor nije poznat. Ovo NIJE greška ni u ranijem ni u
sadašnjem radu — okolnosti (korisnikova eksplicitna svijest o pravnom
riziku) su se promijenile, i tretirano je kao važeća, namjerna promjena
politike, ne kao "ispravka bug-a". Dokumentovano eksplicitno u kodu
(komentar u `decide_tariff_match`), test-nazivima, commit poruci i ovom
izvještaju da bi budući agent/developer razumio KONTEKST obje odluke ako
naiđe na ovu istoriju.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `5a53d08` | fix(tariff): nikad ne prikazuj istorijski prijedlog bez potvrdjenog izvora |

## Rizici / ograničenja
- **Smanjena korisnost prijedloga za starije podatke**: zapisi u
  `catalogs.product_tariff_mapping` naučeni PRIJE nego što je izvor počeo
  dosljedno da se bilježi (mnogi visoko-korišteni, "zlatni" zapisi) se
  SADA nikad ne prikazuju kao prijedlog, bez obzira na to koliko su puta
  ranije korišteni. Jedini način da se vrate je popuniti `supplier`/
  `source` kolonu za te zapise (ručna ili skriptovana korekcija podataka
  — NIJE urađeno u ovom zadatku, van scope-a).
- Agent chat tarifni alat (`_prikaz_tarifnih_trenutnih`) i offline eval
  skripta (`scripts/agent_tariff_eval_report.py`) automatski nasljeđuju
  ovu stroziju politiku (dijele `decide_tariff_match`) — nisu posebno
  testirani u OVOM zadatku van postojećeg testa koji već pokriva
  `evaluate_case`/fixture flow.

## Potreban follow-up
- Razmotriti skriptu koja bi retroaktivno popunila `supplier`/`source`
  kolonu za postojeće visoko-korištene zapise bez izvora (npr. iz XML
  arhive ako je dokaz dostupan) — vratilo bi korisnost bez slabljenja
  nove politike.
- `agent_tariff_eval_report.py` metrike (true_positive/true_negative) će
  se promijeniti za BILO KOJI budući skup test-fakture — vrijedi ponovo
  pokrenuti eval report na punom setu stvarnih faktura da se izmjeri
  stvaran pad "recall"-a (koliko manje prijedloga sistem sad daje).

## Potrebna korisnička potvrda
Nema — odluka je eksplicitna i jednoznačna, implementacija direktno
odgovara traženom ponašanju.
