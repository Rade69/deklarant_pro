# Auto-detekcija pariteta isporuke (Incoterms) iz faktura

## Cilj

Rubrika 20 "Uslovi isporuke" (`draft.uslovi_kod`) u Zaglavlju se trenutno
NIKAD ne popunjava automatski — korisnik je uvijek ručno unosi, iako se
paritet (EXW/FCA/FAS/FOB/CFR/CIF/CPT/CIP/DAP/DPU/DDP) često pojavljuje kao
prepoznatljiv tekst na fakturi. Dva postojeća importer-a (KG Fashion,
Master Frigo) to već hvataju regexom, ali vrijednost se gubi prije nego
stigne do `ImportResult`/drafta.

Korisnička odluka (eksplicitno obrazložena — paritet je pravno obavezan
podatak u postupku carinjenja): implementirati kroz SVE importere,
uključujući buduće. Samo šifra pariteta (ne i mjesto isporuke — previše
rizično parsirati iz slobodnog teksta). Ako se ne pronađe pouzdano, polje
ostaje prazno za ručni unos — nikad pogrešan pogodak.

## Pogođeno (GitNexus impact)

- `ImportResult` (upstream): **CRITICAL** — 115 impacted, 73 direktno
  (svi importeri, `ImportService`, GUI). Izmjena je additive (2 nova
  opciona polja sa default `""`), ne dira postojeća polja niti postojeće
  pozive konstruktora.
- `ImportService.import_file()`: 4 return mjesta gdje se poziva
  `_normalize_tariffs_in_result()` — dodaje se analogan poziv za incoterm.
- `FakturaView._apply_import_result_to_header()`: dodaje se treće polje
  (`uslovi_kod`) uz postojeći "samo ako je prazno" obrazac
  (izvoznik/uvoznik/valuta).
- ~12 importer fajlova (`importers/vendors/*/*.py` + `generic_pdf_importer.py`)
  dobijaju jedan dodatni kwarg (`raw_text=full_text`) na mjestu gdje već
  konstruišu `ImportResult(...)`.

## Plan (REVIDIRANO — jednostavnije od prve verzije)

Prvobitna ideja (raw_text polje + centralna detekcija u ImportService,
analogno `_normalize_tariffs_in_result`) odbačena: zahtijevala je DVA nova
polja na `ImportResult` (CRITICAL-impact klasa) i dodatnu izmjenu u
`ImportService.import_file()`. Umjesto toga — isti stil kao već postojeće
`consumed_paths` pravilo (dokumentovana MORA-konvencija, ne centralno
nametnuta): svaki importer sam poziva zajedničku funkciju.

1. `importers/incoterm_utils.py` (nov fajl) — `detect_incoterm(text) -> str`,
   samo label+kod obrasci (Incoterms/Paritet isporuke/Uslovi isporuke/
   Delivery terms + jedan od 11 važećih kodova), BEZ blind standalone
   pretrage koda bez konteksta (izbjegava lažne pozitive).
2. `importers/import_result.py` — dodati SAMO `incoterm_code: str = ""`
   (jedno novo polje, ne dva).
3. Svaki od ~12 importer fajlova (11 vendor + generic_pdf_importer.py) —
   pozvati `detect_incoterm(full_text)` na mjestu gdje već ekstraktuju
   tekst, proslijediti `incoterm_code=...` u `ImportResult(...)`. Za KG
   Fashion/Master Frigo — zamijeniti njihov lokalni regex pozivom na
   `detect_incoterm()` (single source of truth za regex logiku).
4. `gui/tabs/faktura_view.py::_apply_import_result_to_header()` — upisati
   `draft.uslovi_kod = result.incoterm_code` samo ako je `uslovi_kod`
   prazan.
5. `AGENTS.md` — nova stavka u "Parseri (importers/)" sekciji: svaki nov
   importer MORA pozvati `detect_incoterm()` i proslijediti kao
   `incoterm_code` (isti stil/mjesto kao postojeće `consumed_paths`
   pravilo) — ako izostane, Rb.20 za tog dobavljača jednostavno ostaje
   prazan (nije greška, samo propuštena auto-popuna).
6. Testovi: `detect_incoterm()` (više formulacija + no-match slučajevi),
   `_apply_import_result_to_header` (samo ako prazno), wiring test za
   KG Fashion/Master Frigo (regex zamijenjen, ponašanje isto ili bolje),
   sync dist_client mirror za sve dirane fajlove.

GitNexus impact nakon revizije: `ImportResult` i dalje CRITICAL po
topologiji (centralna klasa), ali izmjena je SAMO jedno dodatno opciono
polje sa default "" — additive, ne dira `ImportService` niti bilo koji
postojeći poziv konstruktora koji ne navodi `incoterm_code`.

## Šta NE dirati

- `draft.uslovi_mjesto` — ostaje isključivo ručni unos (korisnička odluka).
- Postojeća polja u `ImportResult` — samo dodavanje, ne mijenjanje.
- `catalogs.incoterms` šifarnik tabela — samo čitanje liste važećih kodova
  odatle ako je praktično, bez izmjene šeme.
- XML-based popunjavanje (`xml_importer.py`, `xml_template_service.py`,
  "kopiraj sa prethodne deklaracije") — već radi ispravno za taj put,
  nedirano.

## Konflikti

Nema ranijih agent_report/memory zapisa o ovoj temi — nov zahtjev.
