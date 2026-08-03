## Datum
2026-08-02

## Agent
Claude Code (Sonnet 5)

## Scope
`services/faktura/preference_rules_service.py`, `services/faktura/validation_service.py`,
odgovarajući `dist_client/` zrcalni fajlovi, `tests/unit/test_faktura_confidence_color_rules.py`,
`tests/unit/test_preference_rules_service.py` (novi).

## Status izvora
Nadovezuje se direktno na `tests/unit/test_faktura_confidence_color_rules.py`
(zaključana istorija 6 bugova, memory `2026-06-07_neutralna-boja-zemlje-
bez-povlastice.md`) — aktivan, sada dopunjen za ovu izmjenu.

## Impact analiza
GitNexus `impact` za `country_confidence_style` (upstream): risk LOW,
20 impacted symbols (sve unutar `faktura_view.py` row-rendering lanca —
`_apply_country_confidence_color` → `_validate_and_color_row` → `_load_data_
from_draft`/`_validation_pass_chunk`/`_on_bulk_change_tariff`/
`_on_historical_validation_finished`), 0 affected_processes. `detect_changes`
nakon svakog od tri commit-a: risk_level `low`, affected_count `0`.

## Reprodukcija prije izmjene
Originalni zahtjev (feature, ne bugfix): korisnički screenshot pokazao da
CN/TW/BR/RS sve dobijaju identičnu flat neutralnu boju kad povlastica nije
potvrđena — reprodukovano čitanjem `_NEUTRAL_COUNTRY_COLOR` upotrebe u
`country_confidence_style`. Tokom implementacije otkrivena DVA dodatna,
neplanirana nesklada (oba reprodukovana kroz korisnički GUI test +
tooltip dijagnostiku, ne nagađanjem):
1. Zemlja kolona se uopšte nije bojila kad `country_confidence` nije
   postavljen (čest slučaj za Assembly/master-list uvoz) — reprodukovano
   direktnim pozivom `country_confidence_style()` sa praznim confidence.
2. PDF_OZNAKA specifično žuto upozorenje davalo je DRUGAČIJU boju od
   "običnog" grupnog reda ISTE zemlje — reprodukovano hover-tooltip
   dijagnostikom na stvarnim redovima (RS red 45 žut, RS red 49 ljubičast,
   tooltip tekst potvrdio dva različita koda puta).

## Kontekst korišćen
Cio `services/faktura/preference_rules_service.py` i `services/faktura/
validation_service.py` pročitani prije izmjene. Cio `tests/unit/test_
faktura_confidence_color_rules.py` pročitan (locked test file, istorija
6 bugova) prije bilo kakve izmjene testova.

## Šta je urađeno
Tri iterativna commit-a, svaki test-first, svaki GUI-testiran od strane
korisnika prije sljedećeg koraka:

1. **`cb0f468`** — `EU_COUNTRIES`/`CEFTA_COUNTRIES` promovisani u modul-nivo
   konstante (`preference_rules_service.py`), nova `country_preference_
   group()`. `ValidationService` dobija `_COUNTRY_GROUP_COLORS` (EU/CEFTA/
   OTHER_PREF/NONE) + `country_group_color()`. `country_confidence_style`/
   `preference_confidence_style` koriste grupu umjesto flat neutralne boje
   kad povlastica nije potvrđena. Gate promijenjen sa "ima country_
   confidence" na "ima zemlju" (rješava nalaz #1).
2. **`c2f96db`** — dijeljeni `_pdf_oznaka_eligible_unset()` helper; kad se
   ispuni, OBJE kolone (Zemlja i Povlastica) dobijaju istu žutu boju
   umjesto da Zemlja ostane grupna a Povlastica žuta.
3. **`397f6e9`** (finalna odluka nakon korisničkog GUI testa) — boja NIKAD
   ne zavisi od izvora (PDF_OZNAKA ili ne), UVIJEK samo `country_group_
   color`. PDF_OZNAKA specifično upozorenje ostaje ISKLJUČIVO kao tooltip
   tekst, ne kao posebna boja.

## Zašto je urađeno
Korisnički zahtjev: deklarant treba lako vizuelno razlikovati zemlje koje
nikad nemaju povlasticu (CN/TW/BR/US) od EU/CEFTA/ostalih povlašćenih
zemalja koje tek treba provjeriti. Iteracije #2 i #3 nisu bile planirane
unaprijed — otkrivene su isključivo kroz korisnikovo stvarno GUI testiranje
na realnim fakturama (Šumaprom), svaki put dijagnostikovano hover-tooltip
tekstom umjesto nagađanja iz screenshot piksela.

## Kako je urađeno
Za svaku od tri izmjene: test-first (napisan test za NOVO ponašanje,
potvrđeno FAILED na starom kodu, implementirano, potvrđeno PASSED),
zatim pun `pytest tests/unit`, dist_client sync, `gitnexus_detect_changes`,
commit, `npx gitnexus analyze`. Diagnostika #1/#2/#3 rađena isključivo
kroz direktne Python pozive servisnih funkcija sa sintetičkim podacima
koji mimikuju stvarno stanje (ne nagađanjem iz screenshot boja) — kad je
to bilo nedovoljno (dvosmislena razlika između redova), korišćena je
hover-tooltip dijagnostika na STVARNOJ aplikaciji (korisnik prepisao tekst
tooltip-a), što je oba puta dalo jednoznačan odgovor bez dalje nagađanja.

## Šta nije dirano
✅/zelena boja (potvrđena povlastica sa PE1/PE2/PE3 dokazom) — nepromijenjen
istorijski lock iz Kruga 1-3 (memory `2026-06-07_*`). Ostatak `ValidationService`
API-ja (`validate_and_get_style`, `validate_all`, itd.) — netaknut.

## Verifikacija
Nakon svakog od 3 commit-a: `pytest tests/unit -q` zeleno (osim već
poznatog nepovezanog `test_db_tariff_mapping_unknown_product_returns_none`
"mina" bug-a, environment/DB-state zavisan, dokumentovan 2026-08-01,
van scope-a). dist_client sync potvrđen `diff -q`. `gitnexus_detect_changes`
risk `low` sva tri puta. **GUI potvrda na stvarnim podacima (najjači dokaz
po AGENTS.md hijerarhiji)**: korisnik testirao na 3 odvojene stvarne
fakture/uvoza (Šumaprom 059/2022, 48VP/49VP-2026) kroz sve tri iteracije,
zadnja poruka eksplicitno potvrđuje "Sad sve kako treba" uz screenshot koji
pokazuje dosljedno zeleno ✅ za potvrđenu EUPR/CEFTAR povlasticu i bez boje
za CN (nema pravo na povlasticu).

## Nezavisna provjera
- Checker korišćen: NE
- Da li je promjena spremna za prihvatanje: DA — GUI potvrda na stvarnim
  podacima je najjači dostupan dokaz i eksplicitno je data od korisnika;
  nezavisan checker nije zatražen niti se čini neophodnim za ovaj tip
  vizuelne izmjene (ne dira XML export, DB upise, ili tarifno mapiranje).

## Pronađeni problemi
Dva neplanirana nesklada (opisana gore u "Reprodukcija") otkrivena tokom
rada — oba popravljena u istoj sesiji, oba dokumentovana u testovima i
docstring-ovima da se spriječi buduće tiho vraćanje na neku raniju verziju.
GitNexus `impact` alat vraća LOW/0 za Qt-slot-pozvane metode u oba smjera
(ne prati signal/slot konekcije) — ponovo potvrđen poznat opšti oprez, ne
nov nalaz.

## Odbačene opcije
- Opcija: zadržati PDF_OZNAKA žuto kao posebnu boju (Faza c2f96db stanje).
- Zašto je razmatrana: nosi konkretniju/hitniju poruku od generičkog
  grupnog hint-a, teoretski korisno razlikovati "sistem ima razlog da
  posumnja" od "generički moguće podobna zemlja".
- Zašto je odbačena: korisnik je eksplicitno testirao oba stanja uživo i
  prijavio da dvije boje za istu zemlju (žuto vs grupno) izgledaju kao
  nedosljednost, ne kao namjerna dodatna informacija — subjektivna UX
  odluka, korisnik je autoritativan izvor za nju.
- Kada odluku ponovo otvoriti: ako se pokaže da deklarant STVARNO treba
  brzo razlikovati "hitno provjeri" od "generički moguće" slučajeve —
  moguće riješiti drugačije (npr. ikonica/badge umjesto pune boje ćelije).

## Konflikti / kontradiktorni izvori
Nema — sve tri odluke su direktno od korisnika (AskUserQuestion), nema
suprotstavljenih izvora.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `cb0f468` | feat(faktura): boji Zemlja/Povlastica po grupi zemlje umjesto flat neutralne |
| `c2f96db` | fix(faktura): uskladi zutu boju PDF_OZNAKA upozorenja izmedju Zemlja i Povlastica |
| `397f6e9` | fix(faktura): boja Zemlja/Povlastica NIKAD ne zavisi od PDF_OZNAKA izvora |

## Rizici / ograničenja
Nema poznatih preostalih rizika — GUI potvrđeno na 3 stvarne fakture kroz
sve iteracije. Boje (`_COUNTRY_GROUP_COLORS` hex vrijednosti) su proizvoljno
izabrane (plava/ljubičasta/bež/siva) — ako korisnik kasnije poželi drugačije
nijanse, izmjena je trivijalna (samo hex konstante).

## Potreban follow-up
Nema — zadatak potpuno zatvoren, GUI potvrđeno.

## Potrebna korisnička potvrda
Nema — već data (ovaj izvještaj piše se NAKON potvrde "Sad sve kako treba").
