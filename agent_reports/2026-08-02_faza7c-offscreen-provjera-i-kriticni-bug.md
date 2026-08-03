## Datum
2026-08-02

## Agent
Claude Code (Sonnet 5)

## Scope
`gui/tabs/faktura_view.py` (`_on_historical_validation_finished`),
`dist_client/gui/tabs/faktura_view.py`, `tests/unit/test_faktura_view_
provjeri_selekcija.py`.

## Status izvora
Nadovezuje se na `agent_reports/2026-08-02_faktura-3layer-faza7-
zatvaranje.md`, koji je ostavio otvorenim follow-up: "GUI ručna potvrda
korisnika za Faza 7c izmjene (XML uvoz dugme; 'Provjeri' dugme za
istorijsku validaciju tarifa)". Korisnik je tražio da se ta dva toka
istestiraju prije potpunog zatvaranja.

## Impact analiza
GitNexus `detect_changes` (unstaged): risk_level `low`, affected_count `0`.

## Reprodukcija prije izmjene
Za `_on_import_xml`: pokrenut offscreen (QT_QPA_PLATFORM=offscreen) probe
koji stvarno instancira `FakturaTab`, mockuje SAMO `QFileDialog.
getOpenFileName`/`QMessageBox.*` (dijelovi koji zahtijevaju stvaran
ekran), i poziva `tab.view._on_import_xml()` sa STVARNIM ASYCUDA XML
fajlom (`BLAGIĆ-LOREN-17-7.xml`, izvoznikov stvaran export, van
repozitorijuma zbog poslovnih podataka — vidi "Šta nije dirano").
Rezultat: 34 stavke učitano (poklapa se sa `docs/asycuda_parity_
profile_2026-08-01.md`, koji nezavisno navodi "34 stavke i 12 obrazaca"
za isti fajl), tabela popunjena, bez izuzetka.

Za `_on_historical_validation_finished`: isti pristup, ali sa STVARNIM
`InvoiceLine` objektima (ne `MagicMock` kao postojeći testovi) —
otkriveno da `auto_applied` grana upisuje novi tarifni broj SAMO u Qt
tabelu, NIKAD u `draft.invoice_lines[idx].tarifni_broj`. Reprodukovano
sa jednoznačnim dokazom: `row1_tarifni_broj_updated_cell == "85168080"`
ALI `row1_draft_tarifni_broj == ""` (prazan/stara vrijednost) — na
identičnom pozivu koji koristi realan draft model.

## Kontekst korišćen
`docs/asycuda_parity_profile_2026-08-01.md` pročitan da se pronađu
reference na stvarne ASYCUDA XML fajlove korišćene u ranijim parity
provjerama (van repozitorijuma, na `Desktop/DV1/`). `importers/xml_
importer.py` pročitan u cijelosti da se razumije zašto header ostaje
prazan za ovaj konkretan fajl (vidi "Pronađeni problemi").

## Šta je urađeno
1. Napisan i pokrenut jednokratni (ne-commitovan) offscreen probe za
   `_on_import_xml` sa stvarnim ASYCUDA XML fajlom — potvrđeno da cijeli
   button-handler pipeline radi bez greške na realnim podacima.
2. Napisan i pokrenut jednokratni offscreen probe za `_on_historical_
   validation_finished` sa stvarnim `InvoiceLine` objektima — otkriven
   kritičan bug (draft se ne ažurira u `auto_applied` grani).
3. Napisan karakteristični test (`test_provjeri_selekcija_auto_applied_
   upisuje_tarifu_u_draft`) koji dokazuje bug, potvrđeno FAILED na
   starom kodu.
4. Fix: dodat `self.draft.invoice_lines[idx].tarifni_broj = tarif` u
   `auto_applied` petlju (jedan red), poravnavajući je sa `_on_accepted`
   closure-om (dijalog-potvrda putanja), koja je to već radila ispravno.
5. Ponovljen offscreen probe nakon fixa — potvrđeno `row1_draft_
   tarifni_broj == "85168080"` (poklapa se sa Qt ćelijom).

## Zašto je urađeno
Direktan korisnički zahtjev: "Istettiraj pa da to zatvaramo" — nakon što
sam ranije objasnio da GUI ručna potvrda za ova dva toka nije urađena.
Umjesto da samo ponovim postojeće (nedovoljne) mock-testove, odlučeno je
da se uradi najjača moguća automatizovana provjera (offscreen, stvaran
View, stvarni podaci) koja je ODMAH otkrila bug koji je mock-baziran
test sloj strukturno nije mogao uhvatiti.

## Kako je urađeno
Test-first za fix (karakteristični test napisan i potvrđen FAILED prije
izmjene koda, zatim implementiran fix, zatim potvrđeno PASSED). Probe
skripte su pisane u scratchpad direktorijumu (van repozitorijuma) —
NISU commitovane, jer zavise od apsolutne putanje do fajla koji sadrži
stvarne poslovne podatke trećeg lica.

## Šta nije dirano
`_on_import_xml` — nije mijenjan (probe je potvrdio da radi ispravno).
Header ekstrakcija u `XMLImporter._parse_header()` — NIJE popravljena
(vidi "Pronađeni problemi", zaseban pred-postojeći nalaz van scope-a).
Stvarni ASYCUDA XML fajl (`BLAGIĆ-LOREN-17-7.xml`) — pročitan samo za
verifikaciju, NIJE kopiran u repozitorijum niti su njegovi konkretni
poslovni podaci (nazivi/adrese/JIB) navedeni bilo gdje u ovom izvještaju
ili u kodu.

## Verifikacija
`pytest tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/
test_historical_validation_worker.py tests/unit/test_historical_
validation_remap.py` — 27/27 passed. Pun `pytest tests/unit -q` — 1523
passed (isti poznati nepovezani DB "mina" bug, van scope-a). dist_client
sync potvrđen. Offscreen end-to-end probe (najjači dostupan automatski
dokaz za ovaj tip Qt-vezane logike) potvrđuje fix na STVARNO
instanciranom `FakturaTab`-u, ne samo na mock objektima.

**Ograničenje ove verifikacije** (eksplicitno, po AGENTS.md Definition of
Done za GUI): offscreen render NIJE zamjena za stvarnu GUI potvrdu na
pravom ekranu — QFileDialog/QMessageBox su mockovani jer zahtijevaju
stvaran display. Ono što JE potvrđeno: kompletna poslovna logika oba
toka (parsiranje, remapiranje indeksa, upis u draft, upis u tabelu)
radi ispravno na stvarnim podacima. Ono što NIJE potvrđeno: vizuelni
izgled dijaloga, focus/tab redoslijed, ponašanje na stvarnom monitoru.

## Nezavisna provjera
- Checker korišćen: NE
- Da li je promjena spremna za prihvatanje: DA — bug je jednoznačno
  dokazan (ne "izgleda sumnjivo"), fix je minimalan (1 red, poravnava sa
  već postojećim ispravnim obrascem u istom metodu), karakteristični
  test trajno zaključava ispravno ponašanje.

## Pronađeni problemi
1. **KRITIČAN, POPRAVLJEN**: `auto_applied` grana u `_on_historical_
   validation_finished` nije upisivala tarifni broj u draft model (vidi
   iznad).
2. **Nizak prioritet, NIJE popravljen (van scope-a)**: `XMLImporter.
   _parse_header()` vraća prazan header dict za stvarni ASYCUDA export
   fajl korišćen u probi — parser traži `AsycudaDocument`/`Document`/
   `Declaration`/`Header` kao DIREKTNO dijete root elementa, ali stvarni
   ASYCUDA export ima header podatke raspoređene po `Traders`/`General_
   information`/`Identification` kao direktnoj djeci root-a (bez
   omotača). Stavke (`Item` elementi) se parsiraju ispravno jer koriste
   `.//` (bilo gdje u stablu), header ne. Ovo je PRED-POSTOJEĆA
   ograničenost `XMLImporter`-a (ne mijenjano u Fazi 7, koja je samo
   promijenila ŠTA se radi sa već-ekstraktovanim header dict-om, ne KAKO
   se ekstraktuje) — zaseban zadatak ako se odluči da se popravi.

## Odbačene opcije
- Opcija: kopirati `BLAGIĆ-LOREN-17-7.xml` u `tests/fixtures/` kao
  trajni test fixture.
- Zašto je razmatrana: omogućilo bi trajni automatizovani regresioni
  test za `_on_import_xml` sa realnim podacima, ne samo jednokratnu
  probu.
- Zašto je odbačena: fajl sadrži stvarne poslovne podatke izvoznika
  (naziv, adresa, JIB) — AGENTS.md eksplicitno zabranjuje da carinski
  dokumenti sa poslovnim/ličnim podacima završe u repozitorijumu izvan
  onoga što je zadatak stvarno zahtijevao; commitovanje u git bi ih
  trajno učinilo dijelom istorije.
- Kada odluku ponovo otvoriti: ako korisnik eksplicitno odobri
  korišćenje anonimizovane/sintetičke verzije fajla (izvoznik/JIB/adresa
  zamijenjeni izmišljenim vrijednostima) kao trajnog fixture-a.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `dcfbb6d` | fix(faktura): auto_applied istorijski prijedlog nikad nije upisan u draft |

## Rizici / ograničenja
`XMLImporter._parse_header()` ograničenje (nalaz #2 iznad) ostaje —
ručni XML uvoz preko dugmeta "XML" neće popuniti zaglavlje za ASYCUDA
export fajlove sa ovom (čestom, po probi) strukturom. Nije regresija —
oduvijek je tako radilo — ali korisnik treba da zna da zaglavlje možda
neće biti auto-popunjeno pri ovom tipu uvoza.

## Potreban follow-up
Opciono: popraviti `XMLImporter._parse_header()` da traži header
elemente bilo gdje u stablu (ili direktno kao root-ova djeca), ne samo
kao jednonivoske omotače — zaseban zadatak, van scope-a Faze 7c
zatvaranja.

## Potrebna korisnička potvrda
Idealno: jedan stvaran klik na "XML" dugme i na "Provjeri" dugme na
pravom ekranu, kad bude zgodno — ali automatizovana provjera u ovom
izvještaju je najjača moguća bez toga, i već je otkrila i popravila
stvaran bug koji stvarni klik možda ne bi odmah otkrio (vizuelno je
tabela IZGLEDALA ispravno i prije fixa).
