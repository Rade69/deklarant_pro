## Datum
2026-07-28

## Agent
Claude Code (Sonnet 5)

## Scope
- `services/agent/validation/tariff_decision_model.py` + `dist_client/` mirror
- `services/agent/validation/historical_tariff_search_service.py` + `dist_client/` mirror
- `tests/unit/test_historical_tariff_validation.py` (2 testa prepisana, `_thresholds()` dopunjen)
- `tests/unit/test_tariff_validation_dialog.py` (1 nov test)
- `docs/CONTEXT.md` (§88)

## Status izvora
- `agent_reports/2026-07-22_sussina-supplier-filter-fix.md` — aktivan, prvi
  SUSSINA fix (supplier filter), djelimično poništen kasnijom politikom.
- `agent_reports/2026-07-26_izvor-nepoznat-nikad-prikazan.md` — aktivan,
  korisnička odluka o politici koja je (nenamjerno) stvorila cor-22 popravljen
  ovim zadatkom. Ovaj fix NE poništava tu politiku, dopunjuje je.
- Memorija `2026-07-26_sesija-pregled-agent-safe-context-tarifna-politika.md`
  — potvrdila hronologiju (§64→§65) i eksplicitno upozorila da §65
  "poništava" §27/2026-07-22 SUSSINA odluku za slučaj bez izvora — tačno
  taj sukob je danas istražen do kraja.

## GitNexus impact
`decide_tariff_match` (upstream): **HIGH**, impactedCount 11, 3 direktna
pozivaoca (`_is_actionable_match` root+dist_client, `is_actionable_tariff_match`).
Prijavljeno korisniku prije izmjene (implicitno kroz opis rizika u chatu).
Izmjena je aditivna — nov `SHOW_UNCONFIRMED` outcome, postojeće
SHOW_STRONG/SHOW_WEAK/SUPPRESS grane netaknute.
`detect_changes(scope=unstaged)` nakon izmjene: risk_level low, affected_count 0
— sve promjene tačno u dotaknutim fajlovima (root+dist_client+testovi).

## Šta je urađeno
1. Direktnim upitom u `catalogs.product_tariff_mapping` potvrđeno: tri
   "čista" SUSSINA zapisa (650/200/1200 tbl.) → `21069098`, usage 41-47,
   `source`/`supplier` potpuno prazni. Postoji i pogrešna paralelna mapa
   (→ `38249993`, usage=12, poraslo sa 2 otkad je politika §65 aktivna).
2. Pronađen dvoslojan uzrok (vidi "Kako je urađeno").
3. Dodat `TariffDecisionOutcome.SHOW_UNCONFIRMED` — kad izvor nedostaje ALI
   `usage_count ≥ min_usage_for_unsourced_review` (nov prag, 5), prijedlog
   se prikazuje umjesto potpunog suprimiranja.
4. Postojeća UI/evidence infrastruktura (`TariffValidationDialog`,
   `evidence_from_tariff_decision`) zahtijevala je NULA izmjena — već je
   bila projektovana za "prikaži, ali obilježi kao neprovjereno".
5. Root+dist_client paritet za oba dotaknuta servisna fajla (kopirani cijeli
   fajlovi nakon potvrde da nema nesrodnog drift-a).
6. 2 testa prepisana da odražavaju novo (namjeravano) ponašanje, 1 nov test
   dodat na dijalog nivou.

## Zašto je urađeno
Korisnik je prijavio da "Provjeri" ne daje prijedlog za SUSSINA uprkos
jasnoj istoriji, i napomenuo da je ranija popravka (22.07) bila neuspješna.
Istraga je pokazala da 22.07 fix JESTE radio ispravno na svom nivou
(`_search_one` više ne gubi jak zapis), ali ga je 26.07 politika (namjerna,
obrazložena pravnim rizikom) efektivno poništila za baš ovu klasu zapisa —
i usput, nenamjerno, uklonila JEDINI put kojim bi takav zapis ikad mogao
dobiti legitimnu potvrdu.

## Kako je urađeno
**Sloj 1** (zašto izvor nedostaje): pronađeno da `TariffMappingService.
save_mapping()` — putanja za SVAKU ručnu potvrdu/ispravku tarife u
aplikaciji (Naimenovanja "Nauči", Faktura ispravka, agent chat) — nikad
nije primala niti upisivala `source`/`supplier` u SQL. Samo `learn_from_draft()`
(bulk XML) to radi. Ovaj sloj je sistemski (pogađa SVAKI proizvod naučen
ručno, ne samo SUSSINA) ali NIJE popravljen ovim zadatkom (van scope-a,
korisnik odabrao "samo vidljivost" opciju).

**Sloj 2** (pravi cor-22): pratio se cijeli lanac `decide_tariff_match` →
`_is_actionable_match` → `TariffValidationDialog` → `_record_feedback` →
`catalogs.user_feedback` → `_feedback_action` (auto-primjena na sljedećem
uvozu). Utvrđeno: suprimiranje se dešava PRIJE dijaloga, a `user_feedback`
se puni SAMO iz dijaloga — zatvoren krug bez izlaza.

Prije izmjene provjereno da postojeća UI/evidence infrastruktura
(`TariffValidationDialog._make_row`, `evidence_from_tariff_decision`,
`_can_accept_all`) VEĆ ispravno rukuje `DecisionConfidence.UNKNOWN`
nezavisno od `decision_outcome` stringa — potvrđeno čitanjem koda PRIJE
pisanja izmjene, ne pretpostavkom.

Nov prag (`min_usage_for_unsourced_review=5`) namjerno ODVOJEN od
`min_usage_for_weak_source` (2) — "nema izvora" je rizičnije od "slab
izvor", zaslužuje viši bar prije nego se uopšte ponudi na pregled. Prag
izabran da se poklopi sa postojećim `MIN_USAGE_FOR_CROSS_CHAPTER` (5) —
izbjegnuto izmišljanje novog broja bez presedana u kodu.

## Šta nije dirano
- `TariffMappingService.save_mapping()` / `TariffFacade.learn()`/`sync_mapping()`
  — Sloj 1 (zašto izvor nedostaje za NOVE potvrde) namjerno ostavljen za
  eventualni budući follow-up; korisnik je eksplicitno izabrao opciju "samo
  vidljivost", ne "oboje".
- Pogrešan `SUSSINA → 38249993` zapis u bazi (usage=12) — nije brisan/čišćen
  (van scope-a, nema trenutni negativan efekat jer ispravan zapis pobjeđuje
  po `usage_count DESC`).
- `TariffValidationDialog`, `evidence_from_tariff_decision`,
  `_can_accept_all`, `_is_weak_match` — nula izmjena, već ispravno rade.
- Postojeće SHOW_STRONG/SHOW_WEAK/SUPPRESS grane u `decide_tariff_match` —
  netaknute, samo nova grana dodata.
- `dist_client/tests/unit/test_historical_tariff_validation.py` i
  `test_tariff_validation_dialog.py` — bili već zaostali prije ovog zadatka
  (531 vs 571 i 214 vs 252 linija), nisu ažurirani da se izbjegne miješanje
  sa nepovezanim pre-postojećim drift-om. Produkcioni kod JESTE ogledan.

## Verifikacija
- `python -m py_compile` na sva 4 dotaknuta servisna fajla (root+dist_client).
- Ciljani testovi: `test_historical_tariff_validation.py` (36 passed) +
  `test_tariff_validation_dialog.py` (9 passed) — uključujući end-to-end
  test sa STVARNIM SUSSINA podacima (usage=40, source="") koji sad dokazuje
  `validate_lines()` vraća SHOW_UNCONFIRMED umjesto praznog rezultata.
- Provjereno da nijedan JSON fixture case (`tariff_validation_cases.json`)
  ne mijenja ishod — svi "bez izvora" slučajevi imaju usage 1-2, ispod
  novog praga 5.
- Puna svita: **1460 passed** (1459 + 1 nov test), isti pre-postojeći
  nepovezani padovi (tool registry drift, hardkodovana Linux putanja,
  model_benchmark network) — potvrđeno nepovezano sa ovom izmjenom.
- `gitnexus_detect_changes(scope=unstaged)`: risk_level low, affected_count 0.
- Root vs dist_client diff nakon mirroringa: identičan sadržaj (oba servisna fajla).

## Pronađeni problemi
- Sistemski Sloj 1 (save_mapping ne piše izvor) — dokumentovan, nije popravljen,
  vidi "Potreban follow-up".
- Pogrešan SUSSINA→38249993 zapis u bazi — dokumentovan, nema trenutni efekat.

## Konflikti / kontradiktorni izvori
Politika §65 (26.07) i ovaj fix nisu u sukobu — §65 zabranjuje AUTOMATSKU
primjenu bez izvora, ovaj fix samo vraća mogućnost RUČNE potvrde koja je
slučajno (ne namjerno) bila uklonjena istom izmjenom. Tretiram §65 kao i
dalje važeću, aktivnu politiku — ovaj fix je dopuna, ne poništenje.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `8b22281` | fix(tarifa): SHOW_UNCONFIRMED popravlja cor-22 za prijedloge bez izvora |

## Rizici / ograničenja
- Dijalog "Provjeri" će sad prikazivati VIŠE stavki nego prije (sve sa
  usage≥5 bez izvora) — očekivano poboljšanje, ali korisnik treba znati da
  su te stavke jasno obilježene "izvor nepoznat" i zahtijevaju pojedinačnu
  pažnju, ne mogu se masovno prihvatiti.
- Sloj 1 (save_mapping ne piše izvor) ostaje otvoren — SVAKA buduća ručna
  potvrda i dalje neće imati izvor, oslanjajući se na SHOW_UNCONFIRMED prag
  umjesto na pravu potvrdu porijekla. Follow-up bi ovo trajno zatvorio.

## Potreban follow-up
- Sloj 1: dodati `source` parametar kroz `TariffMappingService.save_mapping()`
  → `TariffFacade.learn()`/`sync_mapping()` i sve pozivaoce (Naimenovanja
  "Nauči", Faktura ispravka, agent chat), npr. konstanta `"RUCNA_POTVRDA"`
  kao smislen izvor za ručne potvrde — zatvorilo bi problem trajno za SVE
  buduće proizvode, ne samo za one iznad usage=5 praga.
- Uživo test u aplikaciji: "Provjeri" na SUSSINA stavci treba sad prikazati
  21069098 kao "izvor nepoznat — zahtijeva ručnu potvrdu"; klik "Prihvati"
  treba da ga trajno nauči (sljedeći uvoz iste stavke ide kroz auto-primjenu
  "ranija ručna potvrda").
- Razmotriti čišćenje pogrešnog `SUSSINA→38249993` zapisa ako ikad postane
  praktičan problem (trenutno nije, `usage_count DESC` ga ne pušta naprijed).

## Potrebna korisnička potvrda
- Da li "Provjeri" sad stvarno prikazuje SUSSINA prijedlog u aplikaciji
  (uživo test, van dosega ove sesije bez pristupa pokrenutoj app-instanci).
- Da li Sloj 1 follow-up (izmjena `save_mapping` da piše izvor za buduće
  ručne potvrde) treba uraditi u sljedećoj sesiji.
