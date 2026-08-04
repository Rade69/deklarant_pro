## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Izmjena: `importers/invoice_line_utils.py` (2 nove funkcije), `importers/vendors/blagic/
blagic_loren_pdf_parser.py`, `importers/vendors/imamoglu/imamoglu_pdf_parser.py`,
`importers/packing_list_parser.py`, `importers/invoice_improved_parser.py`,
`importers/generic_pdf_importer.py`, `importers/vendors/cmana/cmana_pdf_parser.py`,
`importers/vendors/pip_food/pip_food_parser.py`, `importers/vendors/sumaprom/
sumaprom_pdf_parser.py`, `importers/vendors/leburic/leburic_pekabesko_importer.py` +
`dist_client/` kopije svih. Novi test: `tests/unit/test_parse_number_consolidation.py`.
`docs/importers/IMPORTERS_BUG_REPORT.md` (status napomena).

## Status izvora
Nastavak `docs/importers/IMPORTERS_BUG_REPORT.md` preporuke #1 (2026-04-03) i
`agent_reports/2026-08-04_importers-folder-dublja-analiza.md` (koji je ovu konsolidaciju
namjerno odgodio kao follow-up). Korisnik je eksplicitno zatražio nastavak ovom sesijom.

## Impact analiza
`gitnexus_detect_changes` (unstaged, prije commita): risk_level LOW, `affected_processes: []`,
svi dotaknuti simboli u očekivanim fajlovima (10 importer fajlova + dist_client kopije).

## Reprodukcija prije izmjene
Prije bilo kakve izmjene, sve implementacije upoređene na 13 test-slučajeva (uklj.
dvosmislene brojeve "1,234"/"1.234", valutne simbole, negativne vrijednosti, prazan string)
+ `inspect.getsource()` byte-diff da se utvrdi da li su razlike samo kozmetičke ili stvarne.
Novi test fajl je PRVO pokrenut PROTIV neizmijenjenog koda — potvrđeno: 10/13 testova
prolazi (konsolidacione grupe već ponašajno identične), 3 testa faluju (dokaz bug-a u
Sumaprom i Leburić funkcijama prije izmjene — vidi "Pronađeni problemi").

## Kontekst korišćen
Pročitano u cijelosti (radi tačnog poređenja logike, ne samo grep): svih 10 `_parse_number`
varijanti (uklj. `_parse_number_cmana`), kanonska `parse_eu_number` u `invoice_line_utils.py`.

## Šta je urađeno
1. Pročitane sve implementacije, pokrenut Python skript koji poziva svih 10 funkcija na 13
   test-slučajeva i grupiše rezultate po vrijednosti — otkrivene tačne tačke razilaženja.
2. `inspect.getsource()` diff potvrdio: `packing_list_parser`/`invoice_improved_parser` su
   byte-identični; `generic_pdf_importer`/`cmana`(generička)/`pip_food` se razlikuju SAMO u
   imenu varijable (`text` vs `s`) i tekstu komentara — isti algoritam.
3. Dodane 2 nove javne funkcije u `invoice_line_utils.py`: `parse_number_permissive()`
   (za Grupu B) i `parse_number_thousands_heuristic()` (za Grupu C), sa docstring
   objašnjenjem KAKO se razlikuju od postojeće `parse_eu_number()` (bitno, da se ne
   pomiješaju u budućnosti).
4. Napisan `tests/unit/test_parse_number_consolidation.py` PRIJE izmjene poziva u
   vendor-fajlovima (test-first) — pokrenut protiv starog koda da potvrdi baseline i
   reprodukuje 2 bug-a (3 padajuća testa).
5. Zamijenjeno 7 lokalnih `_parse_number` definicija importima (`as _parse_number`, tako da
   svi postojeći pozivi unutar fajla ostanu nepromijenjeni):
   - `blagic_loren_pdf_parser.py`, `imamoglu_pdf_parser.py` → `parse_eu_number`
   - `packing_list_parser.py`, `invoice_improved_parser.py` → `parse_number_permissive`
   - `generic_pdf_importer.py`, `cmana_pdf_parser.py` (SAMO generička `_parse_number`, NE
     `_parse_number_cmana`), `pip_food_parser.py` → `parse_number_thousands_heuristic`
6. Popravljen `sumaprom_pdf_parser.py::_parse_number` (vraćao 0.0 za svaki broj sa
   hiljadarskim separatorom) — zamijenjen importom `parse_eu_number`.
7. Popravljen `leburic_pekabesko_importer.py::_parse_number` (gubio predznak na negativnim,
   pogrešno računao brojeve sa oba separatora) — string-parsing grana delegirana na
   `parse_eu_number`, uz očuvanje `None`/`int`/`float` fast-path-a specifičnog za Excel ćelije.
8. Test svita ponovo pokrenuta — svih 13 novih testova prolazi (uklj. prethodno
   padajuća 3, sad dokaz da su bugovi ispravljeni).
9. `py_compile` na svih 10 fajlova + `invoice_line_utils.py`. Puna `pytest tests/ -q`
   (bez DB-zavisnih) — 1663 passed (+13 u odnosu na prethodni baseline), identičan broj
   pre-postojećih fail-ova (3, nepovezano).
10. `dist_client/` sync (10 fajlova + novi test) uz očuvanje CRLF konvencije tog stabla,
    potvrđeno byte-identično nakon CRLF/LF normalizacije.
11. `gitnexus_detect_changes` + reindex, commit `00e84d0`.
12. Status napomena dopunjena u `docs/importers/IMPORTERS_BUG_REPORT.md`.

## Zašto je urađeno
Korisnik je eksplicitno zatražio nastavak konsolidacije nakon što je u prethodnom krugu
(Leburić PDF wiring bug) postalo jasno da "0 poziva" ili "izgleda duplirano" ZAHTIJEVA
provjeru prije izmjene, ne pretpostavku. Ista disciplina primijenjena ovdje: umjesto
slijepog "zamijeni svih 9 sa jednom kanonskom funkcijom" (što bi TIHO promijenilo stvarne
parsirane vrijednosti za nekoliko dobavljača — npr. "1,234" bi promijenilo značenje sa
1.234 na 1234.0 za tri dobavljača), urađeno je grupisanje po DOKAZANOJ ekvivalentnosti.
Usput otkriven drugi, nezavisan bug u Leburić vendoru (isti kao gdje je već popravljen
PDF-wiring bug ranije ovog dana) — konzistentno sa obrascem da je ovaj specifičan vendor
imao više akumuliranih grešaka.

## Kako je urađeno
Vidi "Šta je urađeno". Ključna metoda: dokaz prije pretpostavke — behavioral testiranje
(13 slučajeva) + izvorni byte-diff prije bilo kakve izmjene, karakterizacioni test fajl
napisan i pokrenut PROTIV starog koda prije nego je ijedan poziv promijenjen.

## Šta nije dirano
- `cmana_pdf_parser.py::_parse_number_cmana` — NAMJERNO netaknuto. Hardkodovano pretpostavlja
  SAMO evropski format (drugačije od `parse_eu_number`/generičke heuristike), ali docstring
  eksplicitno kaže da je ovo tunirano za stvarni, poznat CMANA format — nije bug, vendor-tuning.
- Ostatak `IMPORTERS_BUG_REPORT.md` stavki (#4, #6, #10-16) — nisu provjeravane ni u ovom ni
  u prethodnom krugu ove sesije.
- Real-invoice end-to-end test — `najavauvoza/` folder ne postoji u ovom checkout-u (isto
  ograničenje kao prethodni Leburić bugfix). Najjači dostupan dokaz ostaje behavioral
  test-suite + karakterizacioni testovi.

## Verifikacija
- `py_compile` na svih 10 izmijenjenih fajlova + `invoice_line_utils.py` — OK.
- `pytest tests/unit/test_parse_number_consolidation.py -v` — 13/13 passed (poslije izmjene;
  3/13 su namjerno FAILOVALA prije izmjene kao dokaz bug-a, zapisano u ovom izvještaju).
- Puna `pytest tests/ -q -k "not test_db_..."` — 1663 passed, identičan broj pre-postojećih
  fail-ova (3, nepovezano) kao prije ove sesije.
- `dist_client/` sadržajna identičnost potvrđena (CRLF/LF normalizovano poređenje).

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: GitNexus impact LOW, dvostruki dokaz (behavioral test na 13 slučajeva + izvorni
  byte-diff) za sve konsolidacione grupe PRIJE izmjene, karakterizacioni testovi za oba
  bugfixa PRIJE i POSLIJE. Preporučuje se da korisnik potvrdi na realnoj Sumaprom ili
  Leburić fakturi kad bude dostupna (isto ograničenje kao prethodni bugfix — `najavauvoza/`
  ne postoji lokalno).

## Pronađeni problemi
- Novi, prethodno nedokumentovan bug otkriven ovim krugom: `leburic_pekabesko_importer.py
  ::_parse_number` gubio predznak na negativnim brojevima (regex `[^\d.,]` je brisao `-`
  karakter) — ovo NIJE bilo u `IMPORTERS_BUG_REPORT.md` niti u prethodnom Leburić bugfix
  izvještaju istog dana. Treći nezavisan bug pronađen u istom vendoru u istoj sesiji
  (PDF wiring, sad Excel-cell parsing) — vrijedi napomenuti kao obrazac: ovaj vendor
  zaslužuje temeljitiju provjeru ako se ikad dobije realna faktura za testiranje.
- Sumaprom bug (vraćao 0.0 za hiljadarske brojeve) je bio DOKUMENTOVAN u starom izvještaju
  kao "moguć problem" implicitno (preporuka #1 ga je grupisala sa ostalima), ali nije bio
  eksplicitno prepoznat kao bug dok nije direktno testiran.

## Odbačene opcije
- Opcija: zamijeniti SVIH 9-10 funkcija jednom kanonskom `parse_eu_number()`.
- Zašto je razmatrana: to je bio doslovan prijedlog iz `IMPORTERS_BUG_REPORT.md`.
- Zašto je odbačena: dokazano bi promijenilo stvarne parsirane vrijednosti za dobavljače
  koji koriste "3-cifre-iza-separatora = hiljade" heuristiku (generic_pdf_importer, cmana
  generička, pip_food) — npr. cijena "1,234" bi se promijenila sa 1234.0 na 1.234 (1000x
  greška). Ova heuristika je vjerovatno bila namjerno uvedena jer je nešto u realnim
  fakturama za te dobavljače to zahtijevalo — brisanje bez dokaza da NIJE potrebno bilo bi
  isti tip greške kao brisanje Leburić PDF parsera prošli put.
- Kada odluku ponovo otvoriti: ako se ikad dobije realna faktura od nekog Grupa-C
  dobavljača koja pokazuje da heuristika daje POGREŠAN rezultat za taj specifičan slučaj.

## Konflikti / kontradiktorni izvori
`IMPORTERS_BUG_REPORT.md` preporuka #1 je implicitno pretpostavljala da su sve `_parse_number`
implementacije "duplikati" u smislu da rade istu stvar — pokazalo se tačno za 7 od 10, ali NE
za sve. Tretirano kao: originalna preporuka je bila DJELIMIČNO tačna (vrijedna, ispravna
motivacija za konsolidaciju), ali nije provjerila STVARNU ekvivalentnost prije nego što je
predložila "konsolidovati sve" — ovaj krug je tu provjeru dodao.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `00e84d0` | `refactor(importers): konsolidacija 7 dupliranih _parse_number + 2 bugfixa` |

## Rizici / ograničenja
- Sumaprom i Leburić fix-evi mijenjaju STVARNO ponašanje (namjeravano, popravka bug-a) —
  vrijednosti koje su ranije bile 0.0 ili sa pogrešnim predznakom sada će biti tačne. Ovo je
  pozitivna promjena, ali znači da izlaz za te specifične edge-case brojeve neće biti
  identičan kao prije (očekivano i namjeravano).
- Real-invoice end-to-end test nije bio moguć (razlog gore) — ako se pri sledećem susretu sa
  realnom Sumaprom/Leburić fakturom primijeti neočekivano ponašanje, prvo provjeriti ovaj
  commit.

## Potreban follow-up
Preostale `IMPORTERS_BUG_REPORT.md` stavke #4, #6, #10-16 — nisu provjeravane, mogu biti
ili već riješene (kao 5 od 6 provjerenih ranije ovog dana) ili i dalje važeće.

## Potrebna korisnička potvrda
Ako se ikad naiđe na realnu Sumaprom fakturu sa iznosom preko 1000, ili Leburić Excel sa
negativnom korekcijom (storno) ili EU-formatiranim brojem sa hiljadarskim separatorom u
tekstualnoj ćeliji — vizuelno potvrditi da se sada parsira tačno (ranije bi tiho dalo 0.0
ili pogrešnu/pozitivnu vrijednost).
