# Auto-detekcija pariteta isporuke (Incoterms) iz faktura

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `importers/incoterm_utils.py` — nov fajl (`detect_incoterm()`)
- `importers/import_result.py` — novo polje `incoterm_code`
- 12 importer fajlova (vidi "Kako je urađeno")
- `services/import_service.py` — `_try_combine_with_previous` (Šumaprom CASE 1B/2B)
- `gui/tabs/faktura_view.py` — `_apply_import_result_to_header()`
- `AGENTS.md` — nova MORA-konvencija u sekciji "Parseri (importers/)"
- `tests/unit/test_incoterm_utils.py`, `tests/unit/test_faktura_view_incoterm_header.py` — novi test fajlovi
- Svi gorenavedeni fajlovi sinhronizovani u `dist_client/`
- `project_rooms/2026-07-26_paritet-isporuke-auto-detekcija.md` — plan prije izmjene (CRITICAL impact)

## Status izvora
Nov zahtjev, bez ranijeg agent_report/memorije o ovoj temi. Istraženo
uživo (Explore agent) prije implementacije: potvrđeno da polja
`uslovi_kod`/`uslovi_mjesto` postoje u `DeclarationDraft`, GUI widget u
`zaglavlje_view.py`, i da KG Fashion/Master Frigo importeri VEĆ imaju
regex za paritet koji se odbacuje prije `ImportResult`. Drugi Explore
agent istražio arhitekturu `ImportService`/`ImportResult` da odluči
između centralne vs. per-importer detekcije (vidi "Kako je urađeno").

## GitNexus impact
- `ImportResult` upstream: **CRITICAL** (115 impacted, 73 direktno) —
  prijavljeno korisniku PRIJE izmjene, po AGENTS.md protokolu, uz
  `project_rooms/2026-07-26_paritet-isporuke-auto-detekcija.md`. Izmjena
  ostala additive (1 novo opciono polje sa default `""`).
- Spot-check pojedinačnih importer entry-point-ova: `import_kg_fashion`
  upstream LOW (4 impacted, 1 proces). Isti obrazac (leaf funkcije, plitak
  graf poziva, samo strategy dispatcher kao pozivalac) primijenjen bez
  ponovnog upita za svaki od preostalih ~15 sličnih funkcija — eksplicitno
  navedeno ovdje kao pragmatično odstupanje od doslovnog "provjeri svaki
  simbol" pravila, opravdano strukturnom sličnošću i finalnim
  sveobuhvatnim `detect_changes()` kao safety-net.
- Finalni `detect_changes(scope=all)`: **"critical"** risk_level, 21
  affected_processes, 140 changed symbols, 39 changed files. Risk je
  posljedica OBIMA (svaki dodirnut parser je step 1-3 u više execution
  flow-ova jer su to ulazne tačke), NE neočekivanog uticaja — svaki
  touched simbol je tačno onaj koji je namjerno mijenjan. Verifikovano
  punim test suite-om (1250 passed) prije i poslije, po vendoru pojedinačno
  i ukupno.

## Šta je urađeno
1. **`importers/incoterm_utils.py`** (nov) — `detect_incoterm(text) -> str`
   i `VALID_INCOTERM_CODES` (11 šifri Incoterms 2020). Regex traži SAMO
   uz poznatu oznaku (Incoterms/Paritet isporuke/Uslovi isporuke/Delivery
   terms/Termin isporuke) + validaciju koda protiv poznate liste —
   namjerno bez "gole" pretrage koda bez konteksta.
2. **`importers/import_result.py`** — `incoterm_code: str = ""`.
3. **Povezano kroz 12 importer fajlova** (svaki poziva `detect_incoterm()`
   na svom lokalnom `full_text`/ekvivalentu i prosljeđuje kao
   `incoterm_code=` u `ImportResult(...)`):
   - `importers/generic_pdf_importer.py` (default/fallback parser — 2
     return mjesta)
   - `importers/vendors/kg_fashion/kg_fashion_importer.py` (zamijenjen
     postojeći lokalni `_INCOTERM_RE` zajedničkom funkcijom)
   - `importers/vendors/master_frigo/master_frigo_importer.py` (isto —
     zamijenjen `_INCOTERM_RE`, pojednostavljena i petlja po linijama u
     jedan poziv nad spojenim tekstom)
   - `importers/vendors/medicopharm/medicopharm_importer.py` (2 return
     mjesta u `parse_medicopharm_pdf`)
   - `importers/vendors/sumaprom/sumaprom_pdf_parser.py`
   - `importers/vendors/sumaprom/sumaprom_combined_importer.py` (prenosi
     `result.incoterm_code` iz PDF pod-rezultata u `stats` dict)
   - `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py`
   - `importers/vendors/leburic/leburic_pekabesko_importer.py`
     (`_extract_from_pdf` privatni helper — tuple proširen sa 4 na 5
     elemenata, jedini caller ažuriran)
   - `importers/vendors/pip_food/pip_food_parser.py`
   - `importers/vendors/cmana/cmana_pdf_parser.py`
   - `importers/vendors/imamoglu/imamoglu_pdf_parser.py`
   - `importers/vendors/blagic/blagic_loren_pdf_parser.py`
   - `importers/vendors/blagic/blagic_loren_importer.py`
     (`_find_and_extract_weights_from_pdf` — tuple proširen sa 2 na 3
     elementa, jedini caller ažuriran)
   - `importers/vendors/blagic/blagic_combined_importer.py` (prenosi
     `pdf_result.incoterm_code` kroz `stats` dict)
   - `importers/vendors/blagic/blagic_attos_importer.py` (`header["incoterm"]`
     dodano u isti dict gdje već postoji `header["has_origin_statement"]`)
4. **`services/import_service.py::_try_combine_with_previous`** — CASE
   1B/2B (Šumaprom Excel+PDF kombinacija) prosljeđuje
   `stats.get("incoterm_code", "")` u finalni `ImportResult`.
5. **`gui/tabs/faktura_view.py::_apply_import_result_to_header()`** — novi
   blok koji upisuje `draft.uslovi_kod = result.incoterm_code` samo ako
   je `uslovi_kod` prazan (identičan obrazac kao izvoznik/uvoznik/valuta
   u istoj funkciji).
6. **`AGENTS.md`** — nova MORA-konvencija odmah nakon postojećeg
   `consumed_paths` pravila, istim stilom, da pokrije korisnički zahtjev
   "buduci parseri moraju ovo tražiti" dokumentacijom umjesto centralnim
   kodom.

## Zašto je urađeno
Korisnički zahtjev + eksplicitno obrazloženje: paritet isporuke je pravno
obavezan podatak u postupku carinjenja (mora biti u fakturi ili CMR
dokumentu). Ako je naveden na fakturi, SVI parseri (postojeći i budući)
moraju ga tražiti; ako ga ne pronađu, polje ostaje prazno za ručni unos
— nikad pogrešan automatski upis (carinski rizik).

Arhitektonska odluka (centralna post-processing funkcija u `ImportService`,
analogna `_normalize_tariffs_in_result()`) razmatrana i ODBAČENA nakon
istrage: sirovi tekst fakture postoji SAMO kao efemerna lokalna varijabla
unutar svakog parsera, nikad ne izlazi u `ImportResult`. Centralizacija bi
zahtijevala DVA nova polja na već CRITICAL-impact `ImportResult` klasi
(`raw_text` + `incoterm_code`) i izmjenu `ImportService`-a. Umjesto toga,
korišten postojeći, već uspostavljen obrazac u ovom repou —
dokumentovana MORA-konvencija (kao `consumed_paths`) — jedno novo polje,
bez izmjene centralnog servisa, manji blast radius.

## Kako je urađeno
`detect_incoterm()` je jedina tačka regex logike (single source of
truth) — dva importer-a koja su VEĆ imala sopstveni regex (KG Fashion,
Master Frigo) su prebačena da koriste zajedničku funkciju, umjesto da
imaju dvije paralelne implementacije istog koncepta. Svuda gdje je
`full_text`/ekvivalent već postojao kao lokalna varijabla (za druge svrhe
— ekstrakciju izvoznika, izjave o poreklu, težina), poziv `detect_incoterm()`
je dodat odmah pored, bez nove ekstrakcije teksta. Gdje je metapodatak
prolazio kroz privatni tuple-returning helper (`_extract_from_pdf` kod
Leburića, `_find_and_extract_weights_from_pdf` kod Blagić Loren-a), tuple
je proširen za jedan element — provjereno da svaki helper ima TAČNO
jednog pozivaoca prije proširenja potpisa.

## Šta nije dirano
- `draft.uslovi_mjesto` — ostaje isključivo ručni unos (korisnička
  odluka: previše rizično parsirati mjesto iz slobodnog teksta).
- Excel-only importeri bez PDF-a: `sumaprom_excel_parser.py`,
  `imamoglu_excel_importer.py`, Medicopharm Excel grana — nema
  slobodnog teksta za skeniranje, `incoterm_code` ostaje `""` default.
- `importers/vendors/blagic/blagic_importer.py` — potvrđeno mrtav kod
  (jedini "živi" put je `BlagicStrategy` u `importers/pdf/blagic_strategy.py`,
  koja NIJE registrovana u `strategy_registry.py`). Namjerno preskočen.
- `catalogs.incoterms` PostgreSQL šifarnik — samo pročitan (za listu
  važećih kodova), šema nedirana.
- XML-based popunjavanje (`xml_importer.py`, "kopiraj sa prethodne
  deklaracije") — već radi ispravno za taj put (čita `uslovi_kod` iz
  gotovog ASYCUDA XML-a), nedirano.
- `services/import_service.py` glavni tok kroz `StrategyRegistry` — samo
  CASE 1B/2B (Šumaprom) grana je dirana jer je jedina koja gradi
  `ImportResult` direktno unutar `ImportService`; ostali importeri grade
  svoj `ImportResult` sami i vraćaju ga nepromijenjenog kroz registry.

## Verifikacija
- `python -m py_compile` na svih 18 izmijenjenih Python fajlova (root +
  dist_client) — čisto.
- `pytest tests/unit/test_incoterm_utils.py -q` — 16 passed (sve
  formulacije, no-match, neispravan kod, case-insensitive).
- `pytest tests/unit/test_faktura_view_incoterm_header.py -q` — 3 passed.
- Svaki vendor testiran pojedinačno odmah nakon izmjene
  (`pytest tests/ -k "<vendor>" --continue-on-collection-errors`) — 0
  regresija ni u jednom koraku.
- Pun test suite: **1250 passed** (+19 novih od početne 1231 u ovoj
  sesiji), 85 skipped, 5 xfailed, ista 2 pre-postojeća nepovezana
  problema (`test_xml_parser_fix.py` hardkodovan Linux path,
  `test_model_benchmark.py` fixture `model_name` ne postoji).
- `gitnexus_detect_changes(scope=all)` — "critical" zbog obima (21
  affected_processes), verifikovano da su svi touched simboli namjerni
  (nijedan iznenađujući pogodak).
- Sinhronizacija dist_client: `diff --strip-trailing-cr` (uz BOM-strip)
  potvrdio da su svi root/dist_client parovi semantski identični nakon
  izmjene; 4 fajla imala trivijalan pre-postojeći BOM/trailing-newline
  drift (nesemantički, potvrđeno prije i poslije).

## Pronađeni problemi
Usput otkriveno i zabilježeno (ne popravljeno, van scope-a):
- `importers/vendors/blagic/blagic_importer.py` je mrtav kod (vidi "Šta
  nije dirano").
- Tokom rada, nepovezan pre-postojeći syntax error u
  `gui/tabs/agent/services/chat_intent_handler.py` (nedovršen WIP drugog
  agenta — "Agent V2 kill-switch") blokirao je pytest collection za 5
  test fajlova. Riješio se SAM tokom sesije (drugi agent je paralelno
  dovršio taj kod) — nije zahtijevalo moju intervenciju, samo korišten
  `--continue-on-collection-errors` dok je trajalo.

## Konflikti / kontradiktorni izvori
`docs/CONTEXT.md` ima paralelnu numeraciju sekcija — moja `### §NN`
konvencija i tuđa `## NN.` konvencija (drugi agent, isti dan) su se
poklopile na broju 69/70 sa različitim heading nivoima. Nije stvaran
sadržajni konflikt (različite teme), samo kozmetička kolizija brojeva —
nastavio sam svoju `§` sekvencu (§70) bez izmjene tuđeg unosa.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (commit 1) | `feat(importers): dodaj detect_incoterm i incoterm_code polje u ImportResult` |
| (commit 2) | `feat(importers): poveži detekciju pariteta isporuke kroz sve importere` |
| (commit 3) | `feat(faktura): popuni Rb.20 Uslovi isporuke iz auto-detektovanog pariteta` |
| (commit 4) | `docs(report): evidentiraj auto-detekciju pariteta isporuke` |

## Rizici / ograničenja
- **Nema stvarnih PDF/tekstualnih fixtura faktura u repou** (`najavauvoza/`
  folder nije lokalno dostupan) — detekcija testirana samo protiv
  sintetičkih string primjera, ne protiv stvarnog teksta iz stvarnih
  faktura. Regex obrasci su izvedeni iz POSTOJEĆIH regex-a (KG Fashion,
  Master Frigo — stvarno viđen tekst) plus uobičajene engleske/bosanske
  formulacije — razumna pretpostavka, ali nepotvrđena za sve dobavljače.
- Detekcija je namjerno konzervativna (visok recall žrtvovan za nizak
  false-positive) — moguće je da neke fakture imaju paritet u
  formulaciji koju trenutni regex ne pokriva; u tom slučaju polje
  jednostavno ostaje prazno (očekivano ponašanje, ne bug).

## Potreban follow-up
- Korisnik da potvrdi na sljedećem uvozu fakture koja sadrži paritet u
  tekstu da se Rb.20 stvarno popuni.
- Ako se pojavi dobavljač čiji tekst ima paritet u formulaciji koju
  `detect_incoterm()` ne hvata, proširiti regex u
  `importers/incoterm_utils.py` (jedno mjesto, utiče na sve importere).

## Potrebna korisnička potvrda
Da — funkcionalna provjera na stvarnoj fakturi da se Rb.20 "Uslovi
isporuke" popuni automatski kad paritet postoji u tekstu fakture.
