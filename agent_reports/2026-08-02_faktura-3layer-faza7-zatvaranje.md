## Datum
2026-08-02

## Agent
Claude Code (Sonnet 5)

## Scope
`gui/tabs/faktura_view.py`, `gui/tabs/faktura_controller.py`,
`services/export_service.py`, `services/faktura/faktura_service.py`,
`services/faktura/xml_header_extraction.py`,
`services/historical_validation_worker.py`, odgovarajući `dist_client/`
zrcalni fajlovi, `tests/unit/test_*` (7 novih/proširenih fajlova),
`project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`,
`docs/context/history.md`.

## Status izvora
`project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` — aktivan,
kontinuirano ažuriran kroz cijelu sesiju (Faze 1-6 su ranije DONE u ovoj
istoj sesiji/prethodnim, Faza 7 definisana 2026-08-02 nakon svježeg audita
25 `_on_*` metoda, commit `d664f06`). Originalna Faza 7c procjena rizika
(HIGH za oba metoda, na osnovu imena/veličine) je nakon linija-po-linija
čitanja zamijenjena preciznijom — obrazloženo u planu i u ovom izvještaju.

## Impact analiza
GitNexus `detect_changes` (scope unstaged) nakon svake podfaze: risk_level
`low`, `affected_count: 0`, `affected_processes: []` — sve tri podfaze
(7a/7b/7c). GitNexus `impact` upstream/downstream za `_on_item_changed`,
`_on_import_xml`, `_on_historical_validation_finished` (pojedinačno,
target_uid disambiguacija zbog dist_client duplikata): LOW/0 u oba smjera —
očekivano, Qt signal/slot konekcije se ne vide kao pozivi u grafu, pa
stvarna procjena rizika za Fazu 7c dolazi iz ručnog čitanja koda + postojeće
regresione test svite, ne iz alata (napomenuto eksplicitno u planu).

## Reprodukcija prije izmjene
N/A — zadatak je refaktor (izdvajanje poslovne logike), ne bugfix. Za svaku
izdvojenu funkciju napisan je karakterizacioni test PRIJE implementacije,
potvrđeno da FAILUJE (funkcija ne postoji), zatim implementirano, zatim
potvrđeno da PROLAZI — isti obrazac kao Faze 5/6 ranije u sesiji.

## Kontekst korišćen
Cio `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`
pročitan više puta (plan, Faza 6 zaključci, Faza 7 audit). Cio
`gui/tabs/faktura_controller.py` (298 linija) pročitan da se izbjegne
duplikat sa postojećim `bulk_change_tariff`/`reset_assembly` metodama.
`services/faktura/faktura_service.py` i `services/historical_validation_
worker.py` pročitani u cijelosti prije dodavanja novih metoda (konvencije,
postojeći importi). `tests/unit/test_faktura_view_provjeri_selekcija.py`
pročitan u cijelosti — presudan za procjenu rizika Faze 7c (pokazao da već
postoji jaka regresiona svita za baš tu logiku).

## Šta je urađeno
Zatvorena Faza 7 (posljednja otvorena faza troslojnog refaktora Faktura
taba) kroz tri podfaze:

**Faza 7a** (commit `631a33b`): `_on_clear_all` → `WeightManager.
reset_weights()`; `_on_export_excel` → novi `ExportService.
find_unassigned_items()` (4 testa); `_on_load_master_list` → novi
`FakturaController.load_master_list()` (2 testa).

**Faza 7b** (commit `0f9c951`): `_on_item_changed` → novi `FakturaService.
apply_cell_edit()` (14 testova); `_on_bulk_change_tariff` → novi
`FakturaService.bulk_set_tariff()` (6 testova); `_on_load_previous_
declaration` → tri nove funkcije u `xml_header_extraction.py`:
`resolve_exporter_name`, `format_header_preview`, `apply_header_to_draft`
(8 testova).

**Faza 7c** (commit `95b8bd6`, suženog opsega): `_on_historical_validation_
finished` → novi `HistoricalValidationWorker.remap_local_indices()` za
kritično remapiranje lokalnih indeksa (7 testova); `_on_import_xml` →
ponovna upotreba `apply_header_to_draft()` iz Faze 7b, uklonjena mrtva
`updated_count` varijabla.

Nakon svake podfaze: pun `pytest tests/unit -q` run, dist_client sync,
`gitnexus_detect_changes`, commit, `npx gitnexus analyze`.

Plan dokument (`project_rooms/...`) ažuriran nakon svake podfaze (status
PENDING→DONE sa commit hash-em) i dopunjen finalnom "ZATVARANJE" sekcijom
koja iskreno sumira šta je i nije urađeno. `docs/context/history.md` zapis
#131 dodat sa istom sumom + poukom za buduće audite (linija-po-linija
procjena rizika je preciznija od procjene po imenu metode).

## Zašto je urađeno
Korisnički zahtjev (2026-08-02): "Želim da se troslojna arhitektura za tab
faktura potpuno završi i napiši šta je sve ostalo da se može stvarno reci
da je taj posao poptpuno završen" — nakon što je ranija Codex procjena
"~65% završeno" (mjerena brojem linija fajla) bila osporena kao pogrešna
metrika u ranijem dijelu iste sesije.

## Kako je urađeno
Test-first karakterizacioni pristup za svaku ekstrakciju: napisan test za
NOVU funkciju/metodu prije nego što je implementirana, potvrđeno FAILED,
implementirano, potvrđeno PASSED, zatim View prepravljen da poziva novu
funkciju umjesto inline logike. Za Fazu 7c dodatno oslonjeno na postojeću
regresionu svitu (`test_faktura_view_provjeri_selekcija.py`, 9 testova iz
2026-07-21, pisanu baš za bug koji bi ekstrakcija mogla ponovo unijeti) kao
najjači dostupan dokaz da je ponašanje identično nakon izmjene.

Faza 7c je namjerno SUŽENA u odnosu na prvobitnu "cijeli metod je HIGH
rizik" procjenu: nakon čitanja oba metoda linija-po-linija, pokazalo se da
svaki sadrži samo malu, jasno omeđenu poslovnu logiku (par-deset linija)
umotanu u mnogo Qt dijalog/redraw orkestracije. Izdvojena je SAMO poslovna
logika; Qt orkestracija je namjerno ostavljena u View-u kao legitimna
View-sloj odgovornost (3-layer pravilo: View = UI/signali/prikaz, ne samo
"sve što nije baza podataka").

## Šta nije dirano
`self.assembly.*` pozivi u `_finish_import_legacy_path`/
`_process_batch_records_legacy` (nisu `_on_*` handleri, već pokriveno
Fazom 6, potvrđeno grep-om ponovo u ovoj sesiji). Preostalih 17 od 25
`_on_*` metoda (čist Qt wiring ili trivijalno mješoviti, klasifikovani u
originalnom Faza 7 auditu kao "ne dirati" — lista u planu). Checker nalaz
#3 iz `2026-08-02_assembly-eur1-dialog-parity.md` (EUR.1 dijalog
otkazivanje) — eksplicitno van scope-a, dijeli infrastrukturu sa Agent
modom. `AGENTS.md`, `CLAUDE.md`, `dist_client/ui/naimenovanja_tab_
OPTIMIZED_ui.py`, `dist_client/ui/zaglavlje_tab_ui.py` — zatečeni kao
nekomitovan WIP drugog agenta/sesije na početku ovog zadatka (`git status
--short` provjeren prije svakog `git add`), namjerno ostavljeni netaknuti.

## Verifikacija
Nakon svake podfaze: `python -m pytest tests/unit -q -m "not integration"`
— 1503 passed nakon Faze 7c (od 1518 ukupno; 2 padaju: 1 DB test zbog već
poznatog, nepovezanog product_tariff_mapping "mina" bug-a iz memorije
2026-08-01, van scope-a; dist_client sync riješen prije finalnog runa u
svakoj podfazi). `ast.parse` sintaksna provjera na svim izmijenjenim
fajlovima. `TestDistStandalone::test_dist_faktura_modules_match_root`
(10 testova) zeleno nakon svakog sync-a. Za Faza 7c specifično: postojeća
regresiona svita `test_faktura_view_provjeri_selekcija.py` (9 testova) i
`test_historical_validation_worker.py` (8 testova) prolaze NEPROMIJENJENE.

## Nezavisna provjera
- Checker korišćen: NE
- Checker agent/model: N/A
- Šta je checker provjerio nezavisno: N/A
- Koje pretpostavke je pokušao oboriti: N/A
- Šta je potvrđeno: N/A
- Šta nije potvrđeno: N/A
- Da li je promjena spremna za prihvatanje: PARCIJALNO — automatski testovi
  su jaki (uklj. postojeću regresionu svitu za baš rizičnu Faza 7c logiku),
  ali AGENTS.md hijerarhija dokaza stavlja GUI ručnu potvrdu na stvarnim
  podacima iznad automatizovanog testa za HIGH-risk promjene; ta potvrda
  još nije urađena (vidi "Potrebna korisnička potvrda" ispod). Nezavisan
  checker nije pokrenut jer korisnik nije eksplicitno tražio za ovaj
  segment — preporučuje se za Fazu 7c prije potpunog zatvaranja s obzirom
  na compliance-kritičan kontekst (tarifni brojevi u ASYCUDA deklaraciji).

## Pronađeni problemi
Tokom rada: nijedan nov bug pronađen u postojećem kodu (za razliku od
ranijih faza u ovoj sesiji gdje je EUR.1 lanac otkrio 3 stvarna buga). Jedna
mrtva varijabla uklonjena (`updated_count` u `_on_import_xml`, izračunata a
nikad čitana). Jedan nepouzdan GitNexus signal: `impact` alat vraća LOW/0
za oba Faza 7c metoda u oba smjera (upstream i downstream) zbog toga što
graf ne prati Qt signal/slot konekcije niti pozive unutar lokalnih `from
... import` blokova unutar funkcije — ne tretirati "GitNexus LOW" kao
dokaz niskog stvarnog rizika za Qt-slot metode; potrebno je ručno čitanje
koda + postojeći testovi kao stvarni izvor procjene rizika (već poznat
obrazac iz memorije `feedback_gitnexus_line_shift_false_positive.md`, ovdje
nova varijanta istog opšteg opreza).

## Odbačene opcije
- Opcija: forsirati `_on_import_xml` kroz postojeći `import_workflow`
  plan/decision/apply pipeline (isti pipeline koji koriste ostali uvoz
  putevi) umjesto samo izdvajanja header_data logike.
- Zašto je razmatrana: originalni Faza 7 audit je ovaj metod opisao kao
  "cijeli paralelni, NEMIGRIRANI XML-uvoz tok" — implicirajući da bi puna
  migracija bila "prava" ekstrakcija.
- Zašto je odbačena: to bi bila arhitektonska promjena ponašanja (novi
  plan/decision/apply rascjep za tok koji ga nikad nije imao), ne mehanička
  ekstrakcija postojeće logike — direktno kosi AGENTS.md pravilo "ne
  miješati refactor i funkcionalnu izmjenu u istom zadatku". Van scope-a
  korisničkog zahtjeva ("izvuci utkanu logiku", ne "redizajniraj XML uvoz").
- Kada odluku ponovo otvoriti: ako korisnik eksplicitno zatraži unifikaciju
  svih uvoz puteva kroz jedan pipeline kao poseban zadatak.

## Konflikti / kontradiktorni izvori
Originalni Faza 7 plan (komitovan `d664f06`) je klasifikovao oba Faza 7c
metoda kao HIGH rizik "cijeli metod" na osnovu audita imena/veličine
metoda. Nakon linija-po-linija čitanja u ovoj sesiji, stvarna poslovna
logika u oba metoda se pokazala malom i jasno izdvojivom, dok je ostatak
Qt orkestracija koja namjerno ostaje u View-u. Tretirano kao: originalna
procjena rizika ostaje TAČNA (obje promjene JESU rizične da se dirну
neoprezno), ali procjena OBIMA ekstrakcije je bila preširoka. Plan dokument
ažuriran da to eksplicitno objasni umjesto tihog odstupanja od plana.
Korisnička potvrda: NE traži se za ovu odluku — u skladu je sa postojećim
projektnim pravilom "ne miješati refactor i funkcionalnu izmjenu", koje je
korisnik već ranije prihvatio kroz AGENTS.md.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `631a33b` | refactor(faktura): Faza 7a - izdvoji clear_all/export_excel/load_master_list logiku |
| `0f9c951` | refactor(faktura): Faza 7b - izdvoji item_changed/bulk_tariff/previous_declaration logiku |
| `95b8bd6` | refactor(faktura): Faza 7c - izdvoji remapiranje indeksa i header logiku (suzen opseg) |

## Rizici / ograničenja
Faza 7c dira logiku koja upisuje tarifne brojeve u carinsku deklaraciju
(ASYCUDA-bound podatak) — automatski testovi su jaki, ali nisu zamjena za
GUI potvrdu na stvarnim fakturama koju AGENTS.md hijerarhija dokaza
zahtijeva za ovaj nivo osjetljivosti. `faktura_view.py` i dalje ima ~5638
linija — to je OČEKIVANO stanje nakon ovog tipa refaktora (View sloj
zadržava svu Qt logiku), ne indikator nepotpunosti, ali vrijedi eksplicitno
navesti da neko ko mjeri "završenost" brojem linija fajla će pogrešno
zaključiti da posao nije gotov.

## Potreban follow-up
GUI ručna potvrda dva Faza 7c toka na stvarnim fakturama (XML uvoz dugme;
"Provjeri" dugme za istorijsku validaciju tarifa, i sa selekcijom redova i
bez nje). Odluka korisnika o checker nalazu #3 (EUR.1 dijalog otkazivanje)
— zaseban, cross-cutting zadatak, ne dio ovog refaktora.

## Potrebna korisnička potvrda
Da: pokrenuti Faktura tab, uvesti ASYCUDA XML fajl preko "Uvoz XML" dugmeta
i potvrditi da se stavke i zaglavlje popune identično kao prije; selektovati
nekoliko redova, kliknuti "Provjeri" (istorijska validacija tarifa) i
potvrditi da se eventualni prijedlog upiše u TAČAN red (ne u pogrešan) —
ovo je tačan simptom koji je originalni bug iz 2026-07-21 imao.
