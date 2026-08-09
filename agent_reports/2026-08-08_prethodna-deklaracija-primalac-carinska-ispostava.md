## Datum
2026-08-08

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`services/faktura/xml_header_extraction.py`, `dist_client/services/faktura/
xml_header_extraction.py`, `gui/tabs/faktura_view.py`, `dist_client/gui/tabs/
faktura_view.py` (metoda `_on_load_previous_declaration`).

## Status izvora
Bogatija verzija `extract_header_from_xml()` (izvoznik/primalac sa svim
poljima) je postojala u commit-ovima `89cc8be`...`255e203` ranije istog
dana, ali revertovana commit-om `1dedd1a` bez objašnjenog razloga u
poruci — status: **revertovano, razlog nepoznat**. Odlučeno da se NE
vraća stari kod (checkout starog diff-a) nego napiše nezavisno, pošto
razlog reverta nije poznat i stari kod nije nezavisno pregledan (vidi
AGENTS.md "Eksterni/tuđi predlog koda").

## Impact analiza
GitNexus `impact()` za `extract_header_from_xml`: LOW, 0 pogođenih
procesa (jedini caller je `_on_load_previous_declaration`).
`detect_changes(scope=unstaged)` prije commit-a: LOW risk, 0
affected_processes, scope tačno odgovara planiranim fajlovima.

## Reprodukcija prije izmjene
Korisnikov screenshot: dijalog "Pronađena prethodna deklaracija" prikazuje
samo Izvoznika, Državu, Valutu, Incoterm, Tip/Oznaku/Proceduru — nema
Primaoca ni Carinske ispostave. Direktna provjera: `extract_header_from_
xml()` vraćala samo 9 ključeva, bez `primalac_*`/`ured_odredista`. `grep`
potvrdio da `Consignee`/`Office_segment` XPath-ovi nisu postojali u kodu.

## Kontekst korišćen
`docs/flow_previous_declaration.md` (cijeli, ranije pročitan na
korisnikov zahtjev — opisuje TAČNO ovu funkcionalnost kao "riješeno", ali
kod je pokazao suprotno — treći ovakav slučaj u sesiji). `git show
1dedd1a --stat` i puna commit poruka — da se razumije šta je i zašto
revertovano prije re-implementacije. Realan XML fajl
(`H:\New folder\NOVA ASIKUDA\CMANA LEBURIĆ PILETINA.xml`) direktno
inspektovan (`ET.parse` + parent-map XPath lookup) da se potvrdi tačna
struktura `Consignee_name`/`Customs_clearance_office_code` prije pisanja
XPath-ova — nagađanje iz doc tabele nije bilo dovoljno (doc navodi
opšti format, stvaran XML je provjeren direktno).

## Šta je urađeno
1. `extract_header_from_xml()`: dodat `_lines()` helper (multiline split),
   `Consignee_name` (1. linija → `primalac_naziv`, 2. → `primalac_grad`,
   3. → `primalac_adresa`), `Consignee_code` → `primalac_id`,
   `Identification/Office_segment/Customs_clearance_office_code` +
   `Customs_Clearance_office_name` → `ured_odredista` (format "ŠIFRA  NAZIV").
   `Exporter_name` proširen isto (grad/država iz 2./3. linije, ranije samo
   1. linija).
2. `field_labels` dict u `_on_load_previous_declaration` proširen sa
   `primalac_naziv: 'Primalac'` i `ured_odredista: 'Carinska ispostava'`.
3. Popravljen `or` redoslijed u `_enrich_header_from_catalogs` inline
   bloku (izvoznik i primalac adresa/grad/država) — draft (XML) vrijednost
   sad ima prioritet, baza samo popunjava prazna polja.
4. `dist_client/gui/tabs/faktura_view.py`: dodat CIJEL `_enrich_header_
   from_catalogs` blok (nije postojao uopšte) + `ensure_initialized()`
   poziv prije `zaglavlje_tab.load_from_draft()` — identično root-u.

## Zašto je urađeno
Direktan korisnikov zahtjev nakon što je prethodni fix (normalizacija)
proradio i dijalog počeo da pronalazi XML — sljedeći sloj problema je bio
da pronađeni XML nije nosio sve podatke koje korisnik očekuje da vidi i
uveze.

## Kako je urađeno
Struktura realnog XML-a provjerena direktno (ne pretpostavljena iz
doc-a) prije pisanja XPath izraza — `Consignee_name` je pod
`Traders/Consignee/`, `Customs_clearance_office_code`/`Customs_Clearance_
office_name` (napomena: nekonzistentna velika/mala slova u samom XML
schema-u) su pod `Identification/Office_segment/`, ne pod
`Traders/Declarant/` kako je prvobitno pretpostavljeno iz doc tabele.
Funkcija napisana nezavisno (ne kopirana iz revertovanog `1dedd1a` diff-a).

## Šta nije dirano
- `apply_header_to_draft()`, `format_header_preview()`,
  `resolve_exporter_name()` — generičke, nisu trebale izmjenu.
- Logika prioriteta u `find_xml_for_pair` — nedirano (odvojen fix, vidi
  prethodni izvještaj).
- `_ensure_exporter_index_ready()` — nedirano, samo joj se koristi output.

## Verifikacija
- `diff` root/dist_client za oba fajla nakon izmjene → identično (exit 0).
- `python -m py_compile` sva 4 fajla → OK.
- Direktan poziv `extract_header_from_xml()` na realnom XML-u
  (`CMANA LEBURIĆ PILETINA.xml`) → svih 15 polja tačno, uključujući
  `primalac_naziv='LEBURIĆ KOMERC DOO'`, `ured_odredista='BA097012  CI
  Bijeljina'` — tačno vrijednosti koje je korisnik naveo u zahtjevu.
- `pytest tests/unit -q`: 1553 passed (bilo 1552), 71 skipped, 5 xfailed,
  **2 failed** (bilo 3) — `test_dist_faktura_modules_match_root` sada
  PROLAZI kao sporedna posljedica dist_client parity fix-a. Preostala 2
  su ista pre-existing kao ranije (DB test-podatak zagađenje, fixture bez
  `fetchone()`), nepromijenjena.

## Nezavisna provjera
- Checker korišćen: NE
- N/A — LOW GitNexus rizik, verifikovano direktno na realnom XML-u i
  punim test suite-om. `or`-redoslijed fix i dist_client parity dodatak su
  bili usputni nalazi tokom rada na glavnom zahtjevu, oba niskorizična i
  pozitivno verifikovana (test prelazi iz FAIL u PASS).

## Pronađeni problemi
1. Funkcionalnost revertovana bez objašnjenja (`1dedd1a`) — mogući
   nepoznati razlog zašto je prvi pokušaj bio problematičan; nova
   implementacija je pisana pažljivo i provjerena na realnim podacima, ali
   nije nemoguće da isti nepoznat problem postoji i u ovoj verziji ako je
   uzrok bio nešto van samog XPath koda (npr. XML format koji varira po
   dobavljaču — arhiva ima 5700 fajlova, testirano samo na 1).
2. `_enrich_header_from_catalogs` `or`-redoslijed bug (baza prepisuje XML)
   — bio je latentan/neaktivan dok XML nije popunjavao grad/adresu, sada
   popravljen prije nego što je postao aktivan.
3. `dist_client` je u potpunosti nedostajao enrich blok — poznat
   pre-existing nalaz iz ranijih izvještaja danas, sada zatvoren.

## Odbačene opcije
- Opcija: `git cherry-pick`/vratiti diff iz `89cc8be`...`255e203` prije
  reverta.
- Zašto je razmatrana: brže, funkcionalnost je već postojala.
- Zašto je odbačena: razlog reverta nepoznat, stari kod nije nezavisno
  pregledan (AGENTS.md "Eksterni/tuđi predlog koda" zahtijeva pregled
  prije usvajanja), a commit poruke duž tog lanca (npr. "uklonjen duplikat
  _on_load_previous_declaration", "_enrich_header inline — nema slobodne
  funkcije koja prekida klasu") sugerišu da je taj rad bio nestabilan/u
  više iteracija ispravljan prije nego što je u cjelini odbačen.
- Kada odluku ponovo otvoriti: nikad za ovaj konkretan slučaj (nova
  implementacija je već napisana i verifikovana) — relevantno samo kao
  opšta smjernica za buduće slične situacije.

## Konflikti / kontradiktorni izvori
`docs/flow_previous_declaration.md` je (treći put u sesiji) opisivao
funkcionalnost kao gotovu, dok je stvaran kod pokazivao suprotno — kod je
tretiran kao istina. Istorija (`1dedd1a` revert) kontradiktorna sa
docs opisom "Rješenje" — revert je noviji i mjerodavniji za trenutno
stanje koda, ali razlog reverta ostaje nepoznat (vidi "Rizici").

## Commitovi
| Hash | Poruka |
| --- | --- |
| `c9c31a4` | feat(faktura): Prethodna deklaracija — primalac i carinska ispostava |

## Rizici / ograničenja
- Testirano na SAMO JEDNOM realnom XML-u (CMANA/LEBURIĆ) — arhiva ima
  5700+ fajlova sa potencijalno različitim formatima (drugi dobavljači,
  stariji ASYCUDA XML verzije). Ako neki format nema `Office_segment` na
  istoj putanji ili ima drugačiju multiline strukturu za Consignee_name,
  ekstrakcija za taj XML jednostavno ne popuni to polje (bez greške — `_text`/
  `_lines` vraćaju prazno ako element ne postoji), ali nije sistematski
  testirano na uzorku od više dobavljača.
- Razlog prošlog reverta (`1dedd1a`) nikad nije utvrđen — ako se ponovo
  pojavi isti nepoznat problem, ovaj fix bi mogao patiti od istog uzroka.

## Potreban follow-up
Preporuka: testirati "Prethodna deklaracija" na par različitih poznatih
dobavljača (ne samo CMANA) tokom narednih par sedmica stvarnog korišćenja,
da se potvrdi da multiline/Office_segment parsing radi dosljedno kroz
arhivu, ne samo na jednom uzorku.

## Potrebna korisnička potvrda
Ručna provjera u pokrenutoj aplikaciji: dijalog "Pronađena prethodna
deklaracija" za CMANA fakturu treba sad prikazati i "Primalac: LEBURIĆ
KOMERC DOO" i "Carinska ispostava: BA097012  CI Bijeljina"; nakon
"Učitaj", Rb.1 Deklaracija u Zaglavlju treba imati popunjenu carinsku
ispostavu, a polje primaoca treba biti popunjeno.

## Ljudsko usvajanje rezultata
- Odgovorna osoba: <<< >>>
- Izvještaj pročitan u cijelosti: <<< DA/NE >>>
- Ključne odluke razumljive i prihvaćene: <<< DA/NE/PARCIJALNO >>>
- Ključne tvrdnje/rezultati provjereni (ne samo agentova tvrdnja da radi): <<< DA/NE/NIJE PRIMJENJIVO >>>
- Rezultat predstavlja stvarno prihvaćeno stanje: <<< DA/NE >>>
- Dijelovi koji još nisu ljudski potvrđeni: <<< >>>
- Dozvoljena naredna akcija: <<< >>>
