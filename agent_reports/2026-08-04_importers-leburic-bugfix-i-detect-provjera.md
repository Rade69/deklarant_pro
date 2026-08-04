## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Nastavak dublje analize `importers/` foldera (na eksplicitan zahtjev korisnika: "smanjimo
nepotreban kod, da ne ide u produkciju"). Izmjena: `importers/smart_pdf_importer.py` +
`dist_client/` kopija. Provjera (bez izmjene): svi top-level `importers/*.py` fajlovi, svi
vendor `__init__.py` fajlovi, svih 14 `detect_*` funkcija u `importers/vendors/`.

## Impact analiza
GitNexus `impact` na `_parse_leburic_pekabesko`: risk LOW, 1 direktan pozivalac
(`parse_smart_pdf`), 0 affected_processes.

## Reprodukcija prije izmjene
Direktan Python import: `from importers.vendors.leburic.leburic_pekabesko_importer import
parse_leburic_pekabesko_pdf` → `ImportError: cannot import name 'parse_leburic_pekabesko_pdf'
from 'importers.vendors.leburic.leburic_pekabesko_importer'`. Praćen tok u `smart_pdf_importer.py`
da se potvrdi da širok `except Exception` (linija ~107) ovu grešku hvata i tiho pada na
`parse_generic_pdf` — korisnik ne vidi grešku, samo degradiranu tačnost parsiranja.

## Šta je urađeno
1. Sistematski provjereno da li su svi top-level `importers/*.py` fajlovi (excel_importer,
   faktura_xml_parser, proton_system_importer, invoice_line_utils, excel_column_utils,
   incoterm_utils, generic_pdf_importer, packing_list_parser, plugin_loader, base_strategy)
   stvarno korišćeni — svi potvrđeno živi, nema dodatnih orphaned top-level fajlova.
2. Dok se provjeravao status `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py`
   (1503 linije, izgledao orphaned po prvom pogledu — 0 poziva iz `smart_pdf_importer.py`
   dispatch-a) — otkriveno da NIJE mrtav kod nego živ, ispravan kod koji je bio POGREŠNO
   OŽIČEN. `smart_pdf_importer.py::_parse_leburic_pekabesko` je pozivao
   `parse_leburic_pekabesko_pdf` iz POGREŠNOG modula (`leburic_pekabesko_importer.py`,
   Excel-fokusiran, 379 linija) — ta funkcija tamo ne postoji.
3. Provjereno da kombinovani Excel+PDF tok (`parse_leburic_pekabesko_excel` +
   `_extract_from_pdf` helper za bruto/neto/zemlju/paritet) je ODVOJEN, ispravan tok — PDF je
   tu namjerno samo supplement, ne primarni izvor stavki (kod-komentar to i kaže). Bug je
   specifično u SAMOSTALNOM PDF-only dispatch putu (kad korisnik uveze samo skenirani PDF bez
   prateće Excel datoteke).
4. Korisnik pitan (AskUserQuestion) — odobrio odmah popravku (ne odgađanje).
5. Fix: import ispravljen sa `.leburic_pekabesko_importer` na `.leburic_pekabesko_pdf_parser`
   (root + dist_client). Signatura potvrđena identična (`pdf_path: str -> ImportResult`).
6. Verifikacija: direktan Python import sada radi; svih 53 postojećih testova u
   `tests/unit/test_leburic_parsers.py` prolazi (testiraju helper funkcije unutar
   `leburic_pekabesko_pdf_parser.py` — `_clean_tariff`, `_clean_number`, `_parse_qty`, itd.);
   puna `pytest tests/ -q` identična baseline-u (3 pre-postojeća fail-a nepovezana).
7. Skripta za provjeru svih lazy-import ciljeva u `smart_pdf_importer.py` i `excel_importer.py`
   (12 unique import statementa) — svi sada rade, nema drugih sličnih skrivenih grešaka u
   dispatch tabeli za PDF ni Excel format.
8. Provjereni svi vendor `__init__.py` fajlovi (9 paketa) — svi importuju čisto.
9. Provjereno svih 14 `detect_*` funkcija u `importers/vendors/` na stvarnu upotrebu.
   Nalaz: `_detect_pdf_format()` u `smart_pdf_importer.py` koristi SOPSTVENU inline
   text-matching logiku za detekciju formata za SVE dobavljače (BLAGIC/ATTOS, IMAMOGLU,
   BLAGIC_LOREN, MASTER_FRIGO, MEDICO_PHARM, PROTON_SYSTEM, ŠUMAPROM, PEKABESKO, PIP_FOOD,
   KG_FASHION, CMANA) — NE poziva vendor-ove sopstvene `detect_*` funkcije (jedini izuzetak:
   `detect_sumaprom_pdf` kao OCR-fallback za skenirane PDF-ove bez teksta). Ovo je
   ARHITEKTONSKI DOSLJEDAN, namjeran obrazac (centralizovana detekcija + delegirano
   parsiranje), ne slučajan drift — potvrđeno da isti obrazac važi za SVE dobavljače podjednako,
   ne samo za nekoliko. `detect_kg_fashion` i `detect_cmana_pdf` nemaju NIKAKVOG pozivaoca van
   sopstvenog fajla (ni test); ostali `detect_*` se koriste u drugim tokovima (Excel dispatch,
   combined-file matching, testovi karakterizacije).
10. Commit `0f3811d` (bugfix), reindex GitNexus.

## Zašto je urađeno
Korisnik je eksplicitno tražio dublju, sistematsku provjeru cijelog `importers/` foldera radi
smanjenja nepotrebnog koda prije produkcije — ne samo brzu potvrdu funkcionalnosti. Sistematska
provjera "da li je X stvarno korišćen" je usput otkrila da jedan kandidat za "nepotreban kod"
(1503-linijski leburic PDF parser) zapravo NIJE bio nepotreban — bio je neophodan, ispravan kod
osakaćen jednim pogrešnim import path-om. Ovo je direktno suprotno očekivanju "briši nepotrebno"
i zaslužuje posebnu pažnju: da sam slijepo primijenio "0 referenci iz očekivanog pozivaoca ⇒
obriši" test bez provjere da li je SAM POZIVALAC ispravan, obrisao bih jedini ispravan
implementaciju i ostavio bug neotkriven.

## Kako je urađeno
Vidi "Šta je urađeno". Ključna metoda: za svaki fajl koji "izgleda orphaned", umjesto samo
grep-a za pozivaoce, direktno testirati da li se navodni pozivalac STVARNO uspješno importuje
(`python -c "from X import Y"`), ne samo da li grep pronalazi tekstualni match.

## Šta nije dirano
- `detect_kg_fashion`, `detect_cmana_pdf` i ostale "arhitektonski redundantne" `detect_*`
  funkcije — NAMJERNO netaknute. Ovo je dosljedan, projektno-širok obrazac (centralizovana
  detekcija u `smart_pdf_importer.py`), ne slučajna greška — brisanje bi kršilo AGENTS.md
  konvenciju "svaki importer ima detect_* funkciju" i moglo bi pokidati testove
  (`test_parser_regression.py` testira neke od njih direktno kao kontrakt/karakterizaciju).
- 9 dupliranih `_parse_number` implementacija — i dalje follow-up iz prethodnog izvještaja,
  nije dirano ovom rundom.
- Excel-format dispatch (`excel_importer.py`) — provjeren, potvrđeno čist, nije mijenjan.

## Verifikacija
Vidi "Šta je urađeno" tačke 6-8. Real-invoice end-to-end test NIJE moguć — `najavauvoza/` folder
ne postoji u ovom checkout-u (potvrđeno `test -d najavauvoza` → ne postoji). Najjači dostupan
dokaz: direktan reproducibilan Python import test (prije: ImportError; poslije: uspješan) +
signature-match + postojeća unit test svita za helper funkcije unutar popravljenog modula.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: GitNexus impact LOW, jasna reprodukcija greške prije i poslije, puna test svita
  zelena. Preporučuje se ipak da korisnik testira na stvarnoj Leburić/Pekabesko PDF fakturi
  kad je dostupna (vidi "Potrebna korisnička potvrda") jer end-to-end tačnost izlaza
  specijalizovanog parsera nije mogla biti provjerena na realnim podacima u ovoj sesiji.

## Pronađeni problemi
Glavni nalaz je sam bug — vidi gore. Sporedno: `najavauvoza/` folder (referenciran u AGENTS.md
kao izvor realnih faktura za testiranje) ne postoji u ovom lokalnom checkout-u, što ograničava
dubinu verifikacije parser-specifičnih izmjena na ovoj mašini/sesiji.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `0f3811d` | `fix(importers): Leburic/Pekabesko PDF import koristio pogresan modul` |

## Rizici / ograničenja
Fix mijenja STVARNO PONAŠANJE (Leburić/Pekabesko samostalni PDF import će sada koristiti
specijalizovani parser umjesto generičkog fallback-a) — ovo je namjeravana, pozitivna promjena
(popravka bug-a), ali znači da izlaz parsiranja za taj specifičan, rijedak slučaj (PDF bez
prateće Excel datoteke) neće biti identičan kao prije. Nije ručno potvrđeno na realnoj fakturi.

## Potreban follow-up
Isti kao prethodni izvještaj: 9 dupliranih `_parse_number` implementacija (svjesno odgođeno).

## Potrebna korisnička potvrda
Ako se ikad naiđe na stvarnu Leburić/Pekabesko PDF fakturu (bez prateće Excel datoteke) —
uvesti je i vizuelno potvrditi da specijalizovani parser (kolone, footer totali) daje tačnije
rezultate od generičkog fallback-a koji se koristio do sada.
