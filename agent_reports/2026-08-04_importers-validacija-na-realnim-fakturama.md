## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Validacija (bez izmjene koda) prethodnih popravki i šira provjera `importers/` na realnim
fakturama iz `H:\New folder\najavauvoza\` (korisnik dao lokaciju nakon što je prethodni
izvještaj naveo da lokalni checkout nema pristup toj bazi).

## Impact analiza
N/A — nije bilo izmjene koda, samo čitanje/pokretanje postojećih parsera na realnim fajlovima.

## Šta je urađeno
1. Popisan sadržaj `H:\New folder\najavauvoza\` — potvrđene realne fakture za: Blagić Attos,
   Blagić Loren, Master Frigo, Medicopharm, MGM/Proton System, PIP Food, Leburić/Pekabesko,
   Šumaprom, CMANA (samo XML deklaracije + misplaced Leburić fajlovi), Imamoglu (samo Excel).
2. **Leburić PDF wiring fix (commit `0f3811d`) potvrđen na 9 realnih PDF-ova**: 5 se parsira
   ispravno sa realnim, smislenim vrijednostima (npr. `LEBURIĆ-PEKABESKO-00019.pdf`: 15 stavki,
   bruto=13934kg, neto=12472.492kg, tarifni brojevi tačni). 4 imaju probleme — vidi
   "Pronađeni problemi".
3. **Leburić Excel `_parse_number` fix (isti commit) potvrđen** na 3 realna Excel fajla
   (`20-00015.xlsx`, `2000-00015.xlsx`, `koreg fak.xlsx`) — svi se parsiraju ispravno, stvarne
   vrijednosti (količine, cijene, iznosi) izgledaju smisleno. `koreg fak.xlsx` (očekivan test
   za predznak-fix) nije sadržao negativne stavke u praksi — fix ostaje verifikovan sintetičkim
   testom, ne ovim konkretnim fajlom.
4. Testirano 17 realnih PDF-ova preko `smart_pdf_importer.parse_smart_pdf` (isti ulaz kao GUI):
   Blagić Attos (3/3 OK), Blagić Loren (2/2 OK), Master Frigo (3/3 OK), Medicopharm-421 (OK),
   MGM/Proton (2/2, jedna sa "neto_kg=0.0" — provjereno, ISPRAVNO ponašanje, faktura genuinski
   ne navodi neto masu), PIP Food (OK), 639 BiH/BIH 893/BLAGIĆ FAKTURA (Medicopharm/Blagić
   format, OK).
5. Testirana Imamoglu Excel detekcija (`detect_imamoglu_mal_tanimlari`,
   `detect_imamoglu_packing_list`) na 2 realna fajla — oba ispravno prepoznata.
6. Korisnik je zaustavio dalju istragu skeniranih/nečitljivih fajlova ("te sumnjive fakture
   preskoči, ja ću se time pozabaviti kasnije") — istraga tih 100%-neuspjelih slučajeva
   (Medicopharm.pdf, Šumaprom DOC041122) prekinuta na njegov zahtjev.

## Pronađeni problemi (NOVI, otkriveni realnim podacima — NIJE popravljano ovom sesijom)

### 1. Nekoliko Leburić PDF-ova ima izobličen tekst-sloj u samom PDF-u (font-encoding problem)
`LEBURIĆ-PEKABESKO-00018.pdf`, `Faktura-2.pdf`, `Faktura-00005.pdf` imaju TEKST (nisu
skenirane slike), ali `pdfplumber.extract_text()` vraća izobličen rezultat — npr.
"PEKABESK0 AD" (nula umjesto O), cifre i slova izmiješani na nivou karaktera
("l1041 Kadino, llinden"). Ovo je karakteristika PDF-a sa nestandardnim/oštećenim cmap
tabelama fonta, ne OCR problem i ne kod-bug u smislu "loše napisana regex". Specijalizovani
parser (`leburic_pekabesko_pdf_parser.py`, koordinate riječi umjesto flat teksta) je DJELIMIČNO
otporan na ovo — stavke se uglavnom izvuku (npr. `00018.pdf` daje 1 stavku, ali sa
pogrešnim nazivom i iznosom 6438900.0 — očigledno pogrešno), ali footer-regex ekstrakcija
(bruto/neto/paritet preko flat teksta) potpuno promašuje na ovim fajlovima
(`Faktura-00005.pdf`: bruto_kg=0.0 iako se 14 stavki ispravno izvuklo).

**Ovo NIJE popravljeno.** Korisnik je eksplicitno zatražio da se ovi konkretni "sumnjivi"
slučajevi preskoče za sada — biće riješeno posebno.

### 2. Dva PDF-a (Medicopharm.pdf, Šumaprom DOC041122...) su potpuno bez teksta (skenirane
slike, 0 karaktera ekstraktovanog teksta, 1 slika po strani) → `smart_pdf_importer` vraća
0 stavki. `parse_smart_pdf` ima OCR fallback korak (poziva `pytesseract`), ali
`pytesseract` NIJE instaliran u ovom okruženju (`could not import 'pytesseract'` u ranijim
test rezultatima), pa se fallback ne može aktivirati/testirati ovdje. **Ovo NIJE popravljeno**
— korisnik je zaustavio dalju istragu ovih fajlova.

## Šta nije provjereno (van vremena ove sesije)
- CMANA — nema realnog PDF uzorka u ovom dumpu podataka (samo XML deklaracije + Leburić
  fajlovi pogrešno smješteni u CMANA folder), `cmana_pdf_parser.py` nije validiran na realnoj
  fakturi.
- Imamoglu — samo detekcija testirana (2/2 OK), pun `imamoglu_excel_importer` parse tok
  (kombinovanje mal_tanimlari + packing_list) nije testiran do kraja.
- kg_fashion — nema uzorka u ovom dumpu podataka.
- `stanc`/Coppercom folder (sadrži fakturu, JCI, izjave o poreklu) — nije jasno kom
  postojećem vendor-parseru odgovara (možda generic fallback), nije istraženo.

## Verifikacija
Sve gore navedeno je READ-ONLY validacija postojećih parsera — nema izmjene koda u ovom
zadatku, pa nema py_compile/test-suite koraka. Rezultati su direktno iz konzole (zapisano u
ovom izvještaju).

## Zaključak / ocjena
Popravke iz `commit 0f3811d` i `commit 00e84d0` (Leburić PDF wiring, Leburić Excel predznak,
Sumaprom `_parse_number`) su **potvrđene na realnim podacima gdje god je bilo moguće** (Leburić
PDF/Excel — da; Sumaprom — ne, jedini realni uzorak je skenirana slika koju je korisnik
zamolio da se preskoči). Ostali dobavljači testirani ovom rundom (Blagić x2, Master Frigo,
Medicopharm, MGM/Proton, PIP Food) rade ispravno na realnim fakturama — nema novih bugova
otkrivenih kod njih.

Otkriven je jedan NOVI, dublji, nepopravljen problem: nekoliko Leburić PDF-ova ima oštećen
font-encoding koji dovodi do djelimičnog (footer podaci nedostaju) ili potpunog neuspjeha
parsiranja. Korisnik je svjesno odgodio rad na tome.

## Potreban follow-up
1. Leburić font-encoding problem (vidi "Pronađeni problemi" #1) — korisnik je najavio da će
   se sam pozabaviti.
2. OCR fallback (pytesseract) nije testabilan u ovom okruženju — ako se odluči da je OCR
   fallback stvarno potreban za skenirane fakture (Medicopharm.pdf, Šumaprom stil), trebalo bi
   provjeriti da li je pytesseract instaliran u produkcijskom (Windows klijent) okruženju,
   odvojeno od ovog dev okruženja.
3. CMANA, Imamoglu (pun tok), kg_fashion — nisu validirani na realnim podacima, nema poznatog
   uzorka za CMANA/kg_fashion u ovom dumpu.

## Potrebna korisnička potvrda
Nema — ovo je izvještaj o nalazima, ne izmjena koda koja zahtijeva potvrdu.
