# Agent report — ComplianceCheckService: nastavak provjere bez ATB fakture

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `services/agent/validation/declaration_validator_service.py` (+ `dist_client/` mirror) — `ComplianceCheckService.check()`

## Status izvora
Direktan follow-up na `2026-06-15_zavrsna-provjera-dugme.md` (dugme
"Završna provjera", commits 274ed16/e9115a8/d0a02fb) — korisnik je testirao
nov tab "Kompletnost" i primijetio da pretpostavlja samo jedan radni tok
(ATB Faktura → Naimenovanja) i preskače drugi (XML uvoz direktno u
Naimenovanja, bez ATB).

## GitNexus impact
`gitnexus_impact(target="check", direction="upstream", file_path="services/agent/validation/declaration_validator_service.py", kind="Method")`
→ **risk LOW**, `impactedCount: 0`, 0 procesa pogođeno (prije izmjene).

Nakon izmjene, `gitnexus_detect_changes(unstaged)` → `risk_level: "medium"`,
`affected_count: 3`, 3 cross-community procesa ("Check → _normalize_score",
"Check → _get_conn", "Check → _row_to_dict") koji prolaze kroz `check` →
`_check_tariff_codes` → funkcije tarifne baze. Procijenjeno kao OK jer:
- `check()` JESTE realno izmijenjen (to je i cilj zadatka).
- `_check_tariff_codes` i njene lokalne varijable (`bez_tarife`, `indices`,
  `msg`) su prijavljene kao "touched" samo zbog pomjeranja linija unutar
  istog fajla (uneseno ~10 novih linija iznad), nisu logički mijenjane.
- Postojeći radni tok (sa ATB fakturom) producira IDENTIČAN izlaz kao prije
  (verifikovano testom ispod) — flow se i dalje izvršava istim redosljedom
  kad `invoice_lines` nije prazan.

MEDIUM rizik, ne HIGH/CRITICAL → `project_rooms/` fajl nije potreban.

## Šta je urađeno
`ComplianceCheckService.check()` (linija ~806) izmijenjena:
- Ranije: `if not lines: ... return result` — odmah prekidalo SVE provjere
  ako `draft.invoice_lines` praznan, sa porukom "Nema uvezenih stavki
  fakture.".
- Sada:
  1. Ako su i `invoice_lines` i `items` (naimenovanja) prazni → isti stari
     `Issue('warning', 'empty', ...)`, `return result` (nepromijenjeno
     ponašanje za potpuno prazan draft).
  2. Ako su `invoice_lines` prazni ali `items` postoje → doda
     `Issue('info', 'no_invoice_lines', "Nema uvezenih stavki fakture (ATB)
     — provjera nastavlja na osnovu naimenovanja.")`, preskače SAMO provjere
     zavisne od `invoice_lines` (`_check_tariff_codes`,
     `_check_zemlja_porijekla`, `_check_tezine`, `_check_eur1_povlastica`,
     `_check_izvoznik_uvoznik`).
  3. `_check_naimenovanja(draft, result)` i `_check_attached_docs(draft,
     result)` se sada izvršavaju UVIJEK (osim u slučaju 1).

## Zašto je urađeno
Korisnikov radni tok "uvoz XML u Naimenovanja → manja ručna korekcija →
snimanje deklaracije" ne popunjava `draft.invoice_lines` (ATB Faktura tab),
ali popunjava `draft.items` (Naimenovanja). Stari `check()` je u tom slučaju
vraćao samo jedno upozorenje "Nema uvezenih stavki fakture." i ništa drugo
ne provjeravao — što znači da su problemi poput naimenovanja bez tarifnog
broja/šifre postupka (Rub.37) ili nedostatka priloženih dokumenata (Rub.44)
ostajali neotkriveni u "Završnoj provjeri" za taj radni tok.

## Kako je urađeno
Restrukturiran kontrolni tok `check()` u tri grane (potpuno prazno / bez ATB
ali sa naimenovanjima / normalan put sa ATB), bez mijenjanja potpisa
`check()` ili bilo koje od `_check_*` helper metoda — sve postojeće helper
metode pozvane su sa istim argumentima kao prije, samo uslovno. Identična
izmjena ponovljena u `dist_client/` mirroru (fajlovi su bili byte-identični
u relevantnoj sekciji, potvrđeno `diff`).

## Šta nije dirano
- `_check_tariff_codes`, `_check_zemlja_porijekla`, `_check_tezine`,
  `_check_eur1_povlastica`, `_check_naimenovanja`, `_check_izvoznik_uvoznik`,
  `_check_attached_docs` — logika unutar ovih metoda nije mijenjana.
- `EnhancedValidationDialog`, `validate_declaration_full`,
  `_compliance_issue_to_validation_item` (iz prethodnog zadatka) — nova
  `info` severity ('no_invoice_lines') se već mapira preko postojećeg
  `_COMPLIANCE_SEVERITY_MAP['info']` bez izmjena.
- Tab naziv "Kompletnost" — korisnik je primijetio da je naziv "malo
  neintuitivan", ali eksplicitno nije tražio promjenu naziva; nije mijenjano.

## Verifikacija
- `python -m py_compile` na oba fajla — OK.
- Offscreen test (`PYTHONPATH=. PYTHONIOENCODING=utf-8`):
  - Draft: `invoice_lines=[]`, `items=[NaimenovanjeDraft(tariff_code="",
    procedure_code="")]` → issues: `no_invoice_lines` (info),
    `naim_no_tariff` (error), `naim_no_procedure` (warning), `no_docs`
    (warning). `errors=1, warnings=2`.
  - Draft potpuno prazan (`invoice_lines=[]`, `items=[]`) → samo `empty`
    (warning), kao prije fixa.
  - Draft sa 1 `InvoiceLine` bez tarife/zemlje porijekla, `items=[]`
    (postojeći radni tok) preko `validate_declaration_full` →
    `valid=False, error_count=22, warning_count=2, info_count=0,
    compliance_items=3` — IDENTIČNO rezultatu iz prethodnog zadatka
    (prije ove izmjene), regresija nije uvedena.

## Pronađeni problemi
Nema. Sva tri scenarija dala očekivane rezultate, bez lažno pozitivnih.

## Commitovi
| Hash | Poruka |
|------|--------|
| `fcf649c` | fix(validacija): ComplianceCheckService.check ne prekida provjeru ako nema ATB stavki |

## Rizici / ograničenja
- `gitnexus_detect_changes` je vratio MEDIUM (umjesto LOW) zbog procesa koji
  prolaze kroz `check()` i tarifnu bazu — procijenjeno kao bezopasno
  (objašnjeno u "GitNexus impact"), ali ako neki drugi proces (van 3
  identifikovana) implicitno očekuje da `check()` na praznom
  `invoice_lines` odmah vrati SAMO jedan `Issue`, sada može dobiti više
  `Issue` objekata (kad `items` nije prazan). Jedini poznati pozivači su
  `validate_declaration_full` (ovaj projekat, prethodni zadatak) i
  `_compliance_check()` u AI chat handleru — oba iteriraju kroz
  `result.issues`/`result.summary_html()` generički, bez pretpostavke o
  broju stavki.

## Potreban follow-up
- Nema otvorenih stavki vezanih za ovaj fix.
- (Nezavisno, spomenuto od korisnika) Naziv taba/dugmeta "Kompletnost" —
  korisnik smatra da je "malo neintuitivan", ali nije tražio promjenu;
  ostaviti za buduću odluku ako se ponovo pokrene.

## Potrebna korisnička potvrda
- Testirati u GUI-ju radni tok "uvoz XML direktno u Naimenovanja (bez ATB
  Faktura uvoza) → ručna korekcija → Završna provjera" i potvrditi da tab
  "Kompletnost" sada prikazuje provjere naimenovanja/dokumenata umjesto
  praznog "Nema uvezenih stavki fakture.".
