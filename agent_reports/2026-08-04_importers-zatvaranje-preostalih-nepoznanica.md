## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Zatvaranje preostalih nepoznanica iz `agent_reports/2026-08-04_importers-validacija-na-realnim-fakturama.md`:
CMANA (kod-pregled, nema realnog uzorka), kg_fashion (kod-pregled, nema realnog uzorka), pun
Imamoglu tok (realni podaci), OCR fallback dostupnost, preostale `IMPORTERS_BUG_REPORT.md`
stavke #4/#6/#10-16. NEMA izmjene koda ovom sesijom — čisto istraživanje/validacija.

## Šta je urađeno i nalazi

### 1. CMANA — pregled koda (nema realne fakture u dostupnim podacima)
`H:\New folder\najavauvoza\CMANA\` sadrži samo XML ASYCUDA deklaracije (izlazni fajlovi, ne
ulazne fakture) i pogrešno smještene Leburić PDF-ove — nema PDF fakture od CMANA. Pun
`cmana_pdf_parser.py` (466 linija) pročitan u cijelosti.

**Nalaz (nije popravljen, VAN scope-a ove sesije jer dira poslovnu tarifnu logiku)**:
`get_tariff_codes_for_product_name()` (linija 398-465) koristi fuzzy matching za automatsko
popunjavanje tarifnog broja po nazivu proizvoda kad tačna šifra nije nađena — ali prihvata
BILO KOJI rezultat sa `best_score > 0.0` (linija 449), a pozivalac (linija 256) primjenjuje
dodatni filter od samo `similarity > 0.25`. Ovo je DRASTIČNO ispod projektnog standarda
`min_similarity = 0.92` dokumentovanog u AGENTS.md ("ne spuštati bez eksplicitnog razloga") i
potvrđenog kao "Projektni threshold" u `services/decision/evidence_adapters.py:60`. Za
poređenje, `kg_fashion_importer.py` (isti `importers/vendors/` folder) ISPRAVNO koristi
`_HISTORICAL_TARIFF_MIN_SIMILARITY = 0.92` (linija 32). CMANA je jedini vendor-parser koji
odstupa od ovog standarda na ovoliko nizak prag.

**Rizik**: tarifni broj sa ~26% sličnosti naziva se direktno upisuje u `InvoiceLine.tarifni_broj`
bez ikakvog "niska pouzdanost" signala korisniku (za razliku od `kg_fashion_importer.py` koji
postavlja `line.tariff_similarity` i `line.raw["tariff_source"] = "historical_suggestion"` za
transparentnost). Za CMANA fakture sa nepoznatom šifrom proizvoda, ovo može tiho upisati
POGREŠAN tarifni broj u carinski dokument.

**NIJE popravljeno** — dira tarifnu poslovnu logiku (AGENTS.md: promjena centralne poslovne
logike ide u "Agent samo predlaže, korisnik odlučuje" kategoriju), i nema realne CMANA fakture
da se testira efekat izmjene prije/poslije.

### 2. kg_fashion — pregled koda (nema realne fakture u dostupnim podacima)
Nema nijednog kg_fashion uzorka bilo gdje u dostupnim podacima (ni u zip arhivama). Pun
`kg_fashion_importer.py` (610 linija) pročitan u cijelosti.

**Nalaz: kod je dobro napisan, nema pronađenih bugova.** Koristi ispravan `min_similarity=0.92`,
`consumed_paths` (za XLS transport manifest koji se automatski uparuje sa PDF fakturom),
`incoterm_code`, `has_origin_statement`, eksplicitne warning poruke za nedostajuće tarife,
transparentno obilježava tarife iz istorije (`tariff_source`, `tariff_similarity`). Regex
patterni za parsiranje redova (`_TAIL_RE`, C/O detekcija, HS kod ekstrakcija) nisu mogli biti
provjereni na stvarnom layout-u fakture bez uzorka — ostaje neverifikovano da li regex zaista
odgovara realnim KG Fashion fakturama, ali kod sam po sebi ne pokazuje očiglednu grešku.

### 3. Imamoglu — pun tok testiran na realnim podacima
`ExcelImporter().import_excel()` (stvaran GUI entry point) testiran na oba realna fajla iz
`H:\New folder\najavauvoza\iamoglu\`:
- `1 mal tanımları.xls` → 40 stavki, cijene/iznosi ispravno izvučeni (npr. 0.8, 1.65, 4.24 EUR),
  zemlja "TR" tačna. `bruto_kg=neto_kg=0.0` — provjereno da je OČEKIVANO (ovaj format je
  cjenovnik/opis robe, ne nosi podatke o težini).
- `PACKING LIST.xlsx` → 42 stavke, `bruto_kg=2383.0`, `neto_kg=2277.0` ispravno izvučeni,
  zemlja "TR" tačna. `cijena_jed=iznos=0.0` za sve stavke — OČEKIVANO (packing lista ne nosi
  cijene, to je uloga mal_tanımları fajla).
- Napomena: ova dva fajla se importuju NEZAVISNO (svaki kao svoj `ImportResult`), ne spajaju
  se automatski u jedan rezultat sa kompletnim podacima (cijena+težina). Ovo NIJE bug — to je
  kako format inherentno radi (dva odvojena izvora podataka), ali korisnik treba biti svjestan
  da import jednog fajla neće imati i cijene i težine istovremeno.

**Zaključak: Imamoglu radi ispravno**, bez grešaka na realnim podacima.

### 4. OCR fallback (pytesseract) — dostupnost provjerena
`pytesseract` i `pdf2image` NISU instalirani u ovom dev okruženju — ALI ovo je **namjerno,
dokumentovano opciono** (odvojen `requirements-ocr.txt` fajl sa uputstvima za instalaciju
sistemskog Tesseract paketa po platformi, `pyproject.toml` ih navodi kao opcionu
`[project.optional-dependencies]` grupu, ne core zavisnost). **Ovo NIJE bug** — to je
arhitektonska odluka da OCR bude opcioni feature. Ne mogu potvrditi da li je instaliran na
stvarnom produkcijskom Windows klijentu (van dosega ove sesije) — vrijedi provjeriti tamo ako
se oslanja na OCR fallback za skenirane fakture.

### 5. Preostale `IMPORTERS_BUG_REPORT.md` stavke (#4, #6, #10-16)
- **#4 (strategy_registry.py cirkularni import) — POTVRĐENO VEĆ RIJEŠENO.** `xml_strategy.py`
  ima `from importers.xml_importer import XMLImporter` unutar `__init__`, ne na vrhu fajla, sa
  eksplicitnim komentarom "lazy import da se izbjegne circular dependency" — neko je ovo već
  popravio prije ove sesije.
- **#14 (packing_list_parser.py fuzzy match, ne koristi difflib.SequenceMatcher) —
  POTVRĐENO I DALJE VAŽI.** `_fuzzy_match_normalized()` i dalje koristi jednostavan
  containment+Jaccard token-set pristup, ne `difflib.SequenceMatcher` kako stari izvještaj
  preporučuje. Minor — utiče na kvalitet fuzzy-matcha kod kratkih naziva proizvoda, ne na
  ispravnost/sigurnost.
- **#6, #10, #12, #13, #15, #16 — NISU reverifikovane u dubinu ove sesije** (svi već označeni
  kao MINOR/POTENCIJALNI u izvornom izvještaju iz aprila) — ostaju u istom statusu
  "nepoznato, treba provjeru" kao ranije.

## Zašto CMANA nalaz nije odmah popravljen
Isti standard kao ranije ove sesije (Leburić/Sumaprom): popravka bez mogućnosti da se
testira na stvarnoj CMANA fakturi (nema uzorka) nosi rizik da se "popravka" zasnuje na
pretpostavci, ne dokazu. Dodatno, ovo je promjena TARIFNE poslovne logike (koji prag
similarity je prihvatljiv za auto-popunjavanje tarifnog broja) — po AGENTS.md podjeli
odgovornosti, agent SAMO PREDLAŽE za "promjenu centralne poslovne logike (tarifno
mapiranje...)", korisnik odlučuje. Preporuka: podići prag na `min_similarity=0.92` (isti kao
projektni standard i kao kg_fashion) i dodati `raw["tariff_source"]`/similarity transparentnost
po uzoru na kg_fashion, ali ovo treba korisnikovu potvrdu prije izmjene.

## Konflikti / kontradiktorni izvori
Nema.

## Rizici / ograničenja
CMANA nalaz je zasnovan isključivo na čitanju koda (nema realne fakture za potvrdu da se
problem stvarno manifestuje sa niskom pouzdanošću u praksi — moguće da CMANA katalog u bazi
ima dovoljno malo/jasno raznolikih naziva proizvoda da nizak prag rijetko uzrokuje stvarnu
grešku, ali kod dozvoljava scenario gdje bi mogao).

## Potreban follow-up
1. **CMANA fuzzy-match prag** — korisnička odluka: podići na 0.92 (uskladiti sa projektnim
   standardom) ili eksplicitno potvrditi da je 0.25 namjerno (i zašto).
2. Provjeriti da li je pytesseract+Tesseract instaliran na produkcijskom Windows klijentu.
3. Stavke #6/#10/#12/#13/#15/#16 iz starog izvještaja — i dalje neprovjerene.

## Potrebna korisnička potvrda
Odluka o CMANA fuzzy-match pragu (vidi gore) prije bilo kakve izmjene tog koda.
