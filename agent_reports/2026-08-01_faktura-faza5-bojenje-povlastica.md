## Datum
2026-08-01

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`gui/tabs/faktura_view.py`, `dist_client/gui/tabs/faktura_view.py`, `services/faktura/validation_service.py`, `dist_client/services/faktura/validation_service.py`, novi `tests/unit/test_faktura_confidence_color_rules.py` (+ dist_client kopija).

## Status izvora
Osnova: `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` Faza 5 sekcija (aktivan, ova sesija ga je i pisala). 6 memorijskih zapisa iz "Zemlja porijekla / povlastica" porodice pročitano u cijelosti prije izmjene — svi aktivni, korišćeni kao izvor istine za pravila koja se NE SMIJU promijeniti.

## Impact analiza
`gitnexus_impact` na obe metode: LOW rizik, po 1 direktan pozivalac (`_validate_and_color_row`), sve unutar `faktura_view.py`, bez pogođenih execution flows. `gitnexus_detect_changes()` nakon izmjene: risk LOW, 0 affected_processes, touched simboli tačno u scope-u (plus par line-shift lažnih pozitiva na susjednim metodama — poznat obrazac, vidi memory `feedback_gitnexus_line_shift_false_positive.md`).

## Reprodukcija prije izmjene
N/A — nije bugfix, refaktor (premještanje postojećih pravila, ne popravka).

## Kontekst korišćen
Svih 6 memorijskih zapisa "Zemlja porijekla / povlastica" porodice pročitano u cijelosti: `2026-06-07_jib-pdv-labele-zamijenjene.md`, `2026-06-07_qt-userrole-stale-data-zemlja-porijekla.md`, `2026-06-07_dijakritik-normalizacija-zemalja.md`, `2026-06-07_zuto-upozorenje-povlastica-nepodobne-zemlje.md`, `2026-06-07_top5-zemalja-skrivene-u-statusnoj-traci.md`, `2026-06-07_neutralna-boja-zemlje-bez-povlastice.md` (najvažniji — finalno binarno pravilo nakon "tri kruga korekcije"). Takođe pročitan `core/decision/evidence.py::evidence_from_preference` da se tačno razumije `requires_confirmation` semantika prije pisanja test fixtures.

## Šta je urađeno
`_apply_country_confidence_color` i `_apply_preference_confidence_color` u `FakturaView` sada delegiraju odluku (koja boja/ikonica/tooltip za koju kombinaciju) na dvije nove statičke metode u `ValidationService`: `country_confidence_style(item)` i `preference_confidence_style(item)`. Obje vraćaju `dict` (ili `None` kad ćelija ne treba izmjenu) — View primjenjuje rezultat na Qt ćeliju (setData boje, `Qt.UserRole` upis, tooltip merge sa postojećim tekstom) bez ikakve poslovne odluke u sebi. Napisano 10 novih karakterizacionih testova koji direktno kodiraju pravila iz memorije, uključujući eksplicitan regresioni test za "Krug 3" bug (MEDIUM/LOW/CONFLICT confidence bez potvrđene povlastice mora biti neutralna, ne pratiti svoju confidence-boju).

## Zašto je urađeno
Dio Faze 5 iz faznog plana troslojnog refaktora Faktura taba — ovo je zadnja preostala poslovna logika utkana direktno u Qt bojenje ćelije. Korisnik je eksplicitno tražio da OVU fazu (za razliku od Faza 1-4 koje su radili Pi/Codex) uradi Claude direktno, zbog istorije 6 nezavisnih bugova u istoj oblasti — rizik nije "kod ne radi" nego "tiha promjena pravila koja izgleda ispravno".

## Kako je urađeno
1. Pročitano svih 6 memorijskih zapisa PRIJE bilo kakvog čitanja koda.
2. Pročitan trenutni kod obje metode (linije pomjerene od originalnog plana zbog Faza 1-4 — 1479/1553, ne 1462/1536).
3. Napisan karakterizacioni test SA fixture-ima izvedenim iz memorijskih pravila (ne iz koda) — 10 testova, svi prošli protiv nove implementacije prije nego što je View uopšte dirn.
4. `gitnexus_impact` provjera na obe metode (LOW).
5. Ekstrakcija: kod kopiran doslovno u `ValidationService` (bez izmjene logike), View metode svedene na Qt-only pozive.
6. Uklonjen mrtav kod (`_CONFIDENCE_COLORS`, `_NEUTRAL_COUNTRY_COLOR` iz `FakturaView`, `evidence_from_preference` import) — `_CONFIDENCE_ICONS` OSTAO jer ga koristi druga metoda.
7. Mirror u `dist_client/` (fajlovi bili identični prije izmjene, provjereno).
8. Pun test suite + `gitnexus_detect_changes`.

## Šta nije dirano
Sama pravila (koja boja za koju kombinaciju) — nulta izmjena semantike, samo premještanje. `_CONFIDENCE_ICONS` konstanta (i dalje u View-u, koristi je druga metoda van scope-a). `_validate_and_color_row` (pozivalac, netaknut). Pre-postojeći nepovezan WIP (`AGENTS.md`/`CLAUDE.md` gitnexus-stats noise, `dist_client/ui/*.py` Qt-recompile drift) — provjeren `git status --short` prije staging-a, nije uključen u commit.

## Verifikacija
Deterministički testovi (najjači nivo po AGENTS.md hijerarhiji dokaza): 10 novih + pun suite 1433 passed / 1 poznat nepovezan DB nalaz (`product_tariff_mapping` "Test proizvod", nepromijenjen ovom izmjenom). `py_compile` prošao (pre-commit hook). GitNexus detect_changes risk LOW.

**GUI vizuelna verifikacija (screenshot prije/poslije, 4 scenarija) NIJE urađena u ovoj sesiji** — dogovoreno unaprijed da to radi korisnik ručno na stvarnom računaru, jer offscreen render nije dovoljan dokaz za ovu specifičnu oblast (AGENTS.md GUI DoD pravilo + istorija bugova otkrivenih isključivo vizuelno).

## Nezavisna provjera
- Checker korišćen: NE
- Checker agent/model: N/A
- Šta je checker provjerio nezavisno: N/A
- Koje pretpostavke je pokušao oboriti: N/A
- Šta je potvrđeno: N/A
- Šta nije potvrđeno: N/A
- Da li je promjena spremna za prihvatanje: PARCIJALNO — kod-nivo DA (testovi + impact + scope potvrđeni), GUI-nivo čeka korisnikovu ručnu potvrdu

## Pronađeni problemi
Nema. Postojeći kod je već ispravno implementirao finalno (Krug 3) pravilo iz memorije — nije trebalo popravljati logiku, samo je premjestiti.

## Odbačene opcije
- Opcija: proslijediti `eligible_for_pref`/`country_code` kao parametre u `preference_confidence_style` umjesto da funkcija sama računa iz `item`.
- Zašto je razmatrana: manje zavisnosti unutar servisne funkcije.
- Zašto je odbačena: cilj Faze 5 je da PRAVILO bude potpuno samostalno u servisu (agent koji sledeći put mijenja pravilo ne treba da zna da View mora prvo nešto izračunati) — funkcija sad sama importuje `suggest_preference_by_country` i računa sve od `item`, View samo prosljeđuje `item`.
- Kada odluku ponovo otvoriti: ako se pokaže da ova zavisnost (`preference_rules_service` import unutar `validation_service.py`) pravi kružni import problem u budućnosti.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| f397afe | refactor(faktura): Faza 5 - izdvoji bojenje/tooltip pravila Zemlja/Povlastica |

## Rizici / ograničenja
Kod-nivo rizik nizak (LOW impact, deterministički testovi, doslovna kopija logike). Preostali rizik je isključivo u GUI sloju koji automatski test ne pokriva (Qt rendering, boja koja se stvarno vidi na ekranu, redosled kolona) — zato GUI verifikacija ostaje otvorena stavka.

## Potreban follow-up
Korisnik treba vizuelno potvrditi 4 scenarija u realnoj aplikaciji: (1) EU zemlja sa potvrđenom povlasticom — zelena+✅, (2) CEFTA zemlja (npr. Srbija) BEZ potvrde — neutralna siva/plava, BEZ ikonice, (3) zemlja bez mogućnosti povlastice (npr. Kina) — ista neutralna boja kao (2), (4) kolona Povlastica: PDF_OZNAKA + eligible zemlja bez povlastice → žuto upozorenje; ista situacija sa neeligible zemljom (Kina) → BEZ upozorenja.

## Potrebna korisnička potvrda
Screenshot/vizuelna provjera na stvarnom računaru (ne offscreen render) za gornja 4 scenarija prije nego se Faza 5 smatra potpuno zatvorenom u planu.
