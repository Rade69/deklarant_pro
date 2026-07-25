# Codex analiza Faktura taba — popravke

## Datum
2026-07-25

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py` (mirror)
- `services/tariff/tariff_mapping_service.py`
- `tests/unit/test_tariff_mapping_service.py` (novi regresioni test)
- `tests/unit/test_faktura_view_tariff_description_db_path.py` (fix nepovezanog test regresa)
- `docs/CONTEXT.md` (§58)

## Status izvora
- `Downloads/Codex-analiza-faktura-taba.docx` (Codex audit + ChatGPT dodatak) — pročitan u cjelosti
  (extract preko python-docx, 544 linija teksta), SVI navodi verifikovani protiv stvarnog koda
  PRIJE bilo kakve izmjene (12+ konkretnih tvrdnji, sve potvrđene tačne). Tretiran kao aktivan izvor.
- `agent_reports/2026-07-25_e2e-import-provjera-i-medicopharm-fixevi.md` — prethodni report iz
  iste sesije, aktivan, nepromijenjen ovim radom.

## GitNexus impact
- `commit_proposals` (upstream): impactedCount 0, risk LOW (GitNexus ne prati poziv kroz
  `TariffFacade.get_instance()` dinamičku indirekciju; ručno potvrđeno grep-om da postoji
  TAČNO jedan pozivalac u cijeloj bazi koda: `faktura_view.py:5244`).
- `_get_tariff_description` (upstream): impactedCount 0, jedini pozivalac
  `_show_tariff_preview_dialog`.
- `detect_changes(scope=all)` PRIJE commita: 57 promijenjenih simbola, 7 fajlova, **0 affected
  processes, risk_level LOW** — svi promijenjeni simboli tačno odgovaraju namjeravanim izmjenama.

## Šta je urađeno
Popravljeno 7 nalaza iz Codex analize (svi niskog/srednjeg rizika, low blast radius) plus
1 usput otkriven nepovezan test regres:

1. **Dupli red pri "Dodaj"** — `_on_add_item` je sam radio `insertRow()` prije poziva
   `_add_item_to_table()`, koja INTERNO takođe radi `insertRow()` na osnovu trenutnog
   `rowCount()` → jedan prazan + jedan popunjen red za jednu novu stavku. Uklonjen redundantni
   `insertRow()` iz pozivaoca. Dodan i potpuno nedostajući `_push_undo_snapshot()` (Ctrl+Z nije
   poništavao ručno dodatu stavku).
2. **Toolbar trajno onemogućen nakon uvoza** — `_on_import_finished` je imao tri rane `return`
   grane PRIJE `self._set_buttons_enabled(True)`. Premješteno u `finally` blok.
3. **"Očisti sve" ne čisti `invoice_weights`/`source_files`** — dodano čišćenje oba polja.
   `draft.items` (naimenovanja) namjerno OSTAVLJEN netaknut (vidljiv korisnički sadržaj).
4. **Naivni `_parse_number()`** — `"1234.56"` (bez zareza) davao `123456.0`. Sad delegira na
   susjednu `_parse_weight_input()` (auto-detekcija EU/US formata po zadnjem separatoru).
5. **`TariffProposal` kolizija po `line_no`** — dodano `line_index` polje (pozicija u listi),
   `commit_proposals()` uparuje prioritetno po njemu uz `line_no` fallback za ručno sastavljene
   proposale. Dodan regresioni test.
6. **`fill_basic_fields()` mutira prije undo snapshot-a** — `_push_undo_snapshot()` premješten
   prije `fill_basic_fields()` poziva u `_on_auto_fill`.
7. **Excel export tiho izostavlja stavke bez naimenovanja** — dodana preflight provjera i
   upozorenje korisniku u `_on_export_excel` PRIJE poziva `ExportService.export_to_excel`.

**Usput otkriven i popravljen nepovezan test regres**: `test_faktura_view_tariff_description_
db_path.py` je pisan za stariju implementaciju `_get_tariff_description` (§57). Međuvremeni
refaktor (commit `703a68e`, izvan ove sesije) je delegirao logiku na `TariffService.
load_hierarchical_label` sa cache-om na `self` — test je otad tiho pucao jer `object()` kao
lažni `self` ne podržava postavljanje atributa. Nije produkcioni bug (pravi `FakturaView` je
`QWidget`). Popravljen test (lagani stub umjesto `object()`), i usput uklonjen mrtav/nedostižan
drugi `except Exception:` blok (ostatak istog refaktora) u oba (root + dist_client).

## Zašto je urađeno
Korisnik je tražio da se popravi sve što se sigurno može iz Codex analize, uz eksplicitnu
opreznost da se ne ugrozi funkcionalnost. Svaki nalaz je prvo verifikovan protiv stvarnog koda,
zatim popravljen minimalnom, ciljanom izmjenom — bez dirat arhitekturu (QUndoStack redesign,
FakturaController ekstrakcija, revision-tracking sistem, puni ExportPreflightService, PDF
document-context cache, DB connection pooling), što je Codex sam preporučio kao "postepeno
izdvajanje bez velikog jednokratnog prepisivanja", a ChatGPT dodatak eksplicitno kao
"aplikaciji trenutno ne treba nova arhitektura, nego kontrolisana stabilizacija".

## Kako je urađeno
- Za svaki nalaz: pročitan tačan kod oko citiranog reda, potvrđena tvrdnja (npr. grep za sve
  pozivaoce `_add_item_to_table`/`commit_proposals`/`_parse_number` da se utvrdi blast radius
  prije izmjene), zatim minimalna izmjena.
- Za Fix #5 (TariffProposal): provjereno da postoje DVA DRUGA, potpuno odvojena
  `TariffProposal` razreda u projektu (`services/agent/chat/tariff_intent_service.py` i
  `gui/tabs/agent/agent_actions.py`, za Agent chat tok) koji VEĆ koriste pozicioni `line_index`
  — potvrđuje da je pristup ispravan i da bug postoji SAMO u
  `services/tariff/tariff_mapping_service.py` (ručni Faktura tab tok).
- Root vs dist_client `faktura_view.py` diff prije mirroringa: samo 5 očekivanih hunkova
  (Fix #1 i ranija `_get_tariff_description` popravka su već bili mirrorani iz ranijeg dijela
  iste sesije) — nakon mirroringa diff je 0 (fajlovi bit-identični).
- `dist_client/services/tariff_mapping_service` je otkriven kao Nuitka `.pyd`
  (kompajliran 2026-07-18) — fix NIJE mirroran tamo jer nema editabilnog `.py` izvora u
  dist_client za taj modul; rebuild je poseban build korak, van scope-a ovog zadatka.

## Šta nije dirano
- Arhitekturni nalazi iz Codex analize (FakturaView ~6000 linija, 3 konkurentske Faktura
  service API, `draft.items`/`invoice_lines` miksing u `services/faktura_service.py`) —
  eksplicitno deferovano.
- `services/faktura_service.py` — provjereno (grep) da je registrovan u DI kontejneru ali
  NIGDJE resolvovan/pozvan → mrtav kod, `draft.items` mix unutra nema live blast radius,
  nema smisla ga "fixati" jer ništa ga ne izvršava.
- Undo/redo mehanizam (`_push_undo_snapshot`) i dalje snimа SAMO `draft.invoice_lines`, ne i
  `invoice_weights`/`source_files`/zaglavlje polja — poznato ograničenje, van scope-a
  (zahtijeva QUndoStack redesign).
- Performanse (DB konekcije po tarifnom prijedlogu, PDF re-open, deep-copy po cell edit) —
  eksplicitno deferovano, zahtijeva mjerenje prije optimizacije.
- `_sync_table_to_draft()` i editable RB/ordinal kolone — nedirano.

## Verifikacija
- `python -m py_compile` na svim izmijenjenim `.py` fajlovima nakon svake izmjene — OK.
- Novi regresioni test `test_commit_proposals_ne_kolidira_po_line_no_kroz_vise_faktura` —
  simulira dvije fakture sa kolidirajućim `line_no=1`, potvrđuje da svaka stavka dobije SVOJ
  tačan prijedlog nakon fix-a.
- Pun test suite (`python -m pytest tests/ -q`) prije izmjena: 3 failed, 1126 passed, 1 error.
  Nakon izmjena: **1 failed, 1128 passed, 1 error** — preostala 2 su pre-postojeća i nepovezana
  (hardkodovana lična putanja `/home/radovan/...` u `test_xml_parser_fix.py`, nedostajuća
  pytest fixture `model_name` u `test_model_benchmark.py`).
- `gitnexus_detect_changes(scope=all)`: risk_level LOW, 0 affected_processes.

## Pronađeni problemi
- Test regres na `_get_tariff_description` (opisano gore) — nije uzrokovan ovom sesijom
  (uzrok je commit `703a68e`, van vidljivog opsega ove sesije), ali otkriven tokom rutinskog
  `pytest tests/ -q` prije commita i popravljen jer je direktno susjedan kodu koji se već
  mijenjao (dead-code cleanup u istoj metodi).

## Konflikti / kontradiktorni izvori
Nema — Codex analiza tretirana kao jedini izvor za ovaj zadatak, svaki navod nezavisno
verifikovan kodom prije djelovanja (nema ranijeg konkurentskog izvještaja o istim nalazima).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `3ce36de` | fix(faktura): popravi 4 buga iz Codex analize faktura taba |
| `6b6aa3c` | fix(tariff): TariffProposal identitet - line_no kolidira kroz vise faktura |
| `5538265` | test(faktura): azuriraj test za _get_tariff_description nakon N+1 refaktora |

## Rizici / ograničenja
- Fix #5 (TariffProposal.line_index) NIJE u dist_client runtime-u (Nuitka .pyd) — .exe build
  (deklarant_pro.spec, root izvor) JESTE pokriven. Windows dist_client instalacija ostaje
  ranjiva na kolizioni bug dok se `tariff_mapping_service` ne rebuilda.
- Fix #3 (čišćenje `invoice_weights`/`source_files` pri "Očisti sve") namjerno ne čisti
  `draft.items` — ako korisnik očekuje da "Očisti sve" briše i naimenovanja, ostaje zbunjujuće
  (nerazriješeno, van scope-a Codex nalaza #3 koji je fokusiran na export staleness).
- Fix #7 (Excel export upozorenje) je preflight u GUI sloju, ne u `ExportService` — ako se
  export ikad pozove van `_on_export_excel` (npr. batch/CLI export skripta), upozorenje se
  neće prikazati.

## Potreban follow-up
- Rebuild `dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd` pri sljedećem
  Windows deploy ciklusu da pokupi Fix #5.
- Preostali Codex nalazi (arhitekturni dug, performanse, undo/redo puni redesign) — kandidat
  za budući, zaseban, veći zadatak ako korisnik odluči da investira u to.

## Potrebna korisnička potvrda
- Da li "Očisti sve" TREBA i naimenovanja (`draft.items`) da briše, ili je trenutno ponašanje
  (samo invoice_lines/weights/source_files) namjeravano? Ostavljeno kako jeste jer je rizičnije
  nagađati oko brisanja vidljivog korisničkog sadržaja bez eksplicitne potvrde.
