# Naimenovanja uvoz XML - Faza 4: popunjavanje Izvoznika/Primaoca + ciscenje Rub.40 referenci

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/naimenovanja_view.py` (`_apply_xml_import_global_documents`, `_apply_xml_import_to_zaglavlje`)
- `dist_client/gui/tabs/naimenovanja_view.py` (identičan mirror)

## Status izvora
- [2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md](2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md)
  (Faze 1-3, commit `d1fedec`) — **aktivan, ali nekompletan**: implementirao
  je čišćenje Rub.40 referenci i Rb.18/21 izuzeće na nivou
  `zaglavlje_tab.view`/internog drafta, ali ne na zajedničkom `self.draft`.
  Ova faza je DOPUNA, ne zamjena — `_PRESERVE_REFS` mehanizam u
  `gui/tabs/zaglavlje_view.py` (Faza 1-3) ostaje netaknut i dalje važi.
- [2026-06-15_fix-uvoz-xml-naimenovanja-documents-mkdir.md](2026-06-15_fix-uvoz-xml-naimenovanja-documents-mkdir.md)
  (commit `b0a7c2c`) — aktivan, nepovezan (default_drafts_directory fallback),
  netaknut ovom izmjenom.

## GitNexus impact
- `gitnexus_impact(target="_apply_xml_import_global_documents",
  target_uid="Method:gui/tabs/naimenovanja_view.py:NaimenovanjaView._apply_xml_import_global_documents#1",
  direction="upstream")` → **LOW**, 1 direktan poziv (`_on_import_xml`), 0
  procesa, 1 modul ("Tabs").
- `gitnexus_impact(target="_apply_xml_import_to_zaglavlje",
  target_uid="Method:gui/tabs/naimenovanja_view.py:NaimenovanjaView._apply_xml_import_to_zaglavlje#1",
  direction="upstream")` → **LOW**, 1 direktan poziv (`_on_import_xml`), 0
  procesa, 1 modul ("Tabs").
- `gitnexus_detect_changes(scope="unstaged")` (prije commit-a) →
  `risk_level: low`, `affected_processes: []`. Izmijenjeni simboli: obje
  metode + `NaimenovanjeView` klasa + `_load_current_item` (samo
  pomak linija) u oba fajla (gui i dist_client). Ostale touched sekcije
  (AGENTS.md/CLAUDE.md/agent_reports/2026-06-14_*) su pre-postojeći
  necommitovani WIP, nisu dio ovog commit-a.

## Šta je urađeno
1. `_apply_xml_import_global_documents`: prije
   `self.draft.header_attached_documents = global_docs`, postavlja
   `doc.number = ""` za svaki `doc.code != "DIS"` u `global_docs`.
2. `_apply_xml_import_to_zaglavlje`:
   - `data["transport_id"]`/`aktivno_transport`/`aktivno_transport_nat`
     se EKSPLICITNO postavljaju na trenutnu vrijednost iz
     `self.draft` (umjesto `data.pop(...)`).
   - Umjesto `zaglavlje_tab.view.set_data(data, _from_import=True)` +
     `zaglavlje_tab.save_to_draft()`, poziva se
     `self.draft = service.save_to_draft(self.draft, data)`, a zatim
     (ako je tab inicijalizovan) `zaglavlje_tab.load_from_draft(self.draft)`.

Identične izmjene u `gui/` i `dist_client/`.

## Zašto je urađeno
Korisnik je nakon stvarnog testa uvoza ASYCUDA XML-a u Naimenovanja prijavio
dva problema u Zaglavlju:

1. **Izvoznik, Primalac (Uvoznik) i ostala polja "druge kolone" Rubrika
   NISU popunjena** — iako je u prethodnoj fazi obećano da hoće biti.
2. **Rub.40 (Priloženi dokumenti) referenca (3. kolona) je popunjena za SVE
   prikazane šifre (VOZ, OST, PZT, N380, DV1, EUP, DUIM, FTAP, TRP) osim
   N730** — a treba da bude prazna za sve OSIM DIS (broj dispozicije).

**Provjera hipoteze / root cause** (potvrđeno empirijski simulacijom punog
flow-a na `data/knowledge_base/NOVA ASIKUDA/02.xml`):

- **Problem A**: `ZaglavljeService.load_from_xml()` ISPRAVNO vraća
  `izvoznik_r1='BIG BULL FOODS'`, `primalac_id='401219270002'`,
  `primalac_r1='LEBURIĆ KOMERC DOO'` — parsiranje XML-a NIJE problem. Stari
  `_apply_xml_import_to_zaglavlje` je te podatke upisivao samo u
  `zaglavlje_tab`-ov interni `view`/draft preko `set_data()` +
  `zaglavlje_tab.save_to_draft()` — NIKAD na zajednički `self.draft`
  (NaimenovanjaView). Kad korisnik otvori Zaglavlje tab,
  `main_window._on_tab_changed` zove
  `zaglavlje_tab.load_from_draft(self.draft)` sa STARIM (praznim)
  `self.draft.izvoznik_naziv`/`primalac_naziv` i prepisuje prikaz.

- **Problem B**: `_apply_xml_import_global_documents` (poziva se PRIJE
  `_apply_xml_import_to_zaglavlje`) puni
  `self.draft.header_attached_documents = global_docs` sa PUNIM referencama
  iz items' `attached_documents`. Dvije posljedice:
  - `ZaglavljeService.save_to_draft`'s "preserve_codes" mehanizam
    (`{"VOZ","PZT","N730","N380","DIS","DV1","PE1","PE2","PE3"}`,
    `services/zaglavlje_service.py:873-899`) vraća STARU (punu) referencu na
    novi (očišćeni) entry ako je nova prazna — empirijski reprodukovano:
    DV1 `1474` se vraća iako je `_apply_xml_import_to_zaglavlje` već
    očistio `data['attached_documents']`.
  - Za šifre KOJE NISU u `preserve_codes` (OST, FTAP, N380...) — stari kod
    NIKAD nije pisao u `self.draft`, pa `self.draft.header_attached_documents`
    ostaje `global_docs` (pune reference) i `load_from_draft` →
    `set_data(data)` (bez `_from_import=True`) prikazuje broj "as-is".
  N730 je slučajno ispravan jer ga (u korisnikovom XML-u) vjerovatno nema u
  `global_docs`, pa nije imao šta da se "vrati"/prikaže.

## Kako je urađeno
Vidi "Šta je urađeno". Tehnički, fix presijeca OBA mehanizma kvarenja na
izvoru:
- `global_docs` (koji postaje `previous_docs` u `save_to_draft`) više nema
  pune non-DIS reference → preserve_codes nema šta vratiti, a eventualni
  reload prije Faze 2 ne prikazuje pune reference.
- `save_to_draft(self.draft, data)` upisuje izvoznik/primalac/itd direktno
  na isti `self.draft` objekat koji `_on_tab_changed` kasnije čita —
  nema više desinhronizacije sa "internim" draftom `zaglavlje_tab`-a.

## Šta nije dirano
- `services/zaglavlje_service.py` (`save_to_draft`, `load_from_draft`,
  `load_from_xml`, preserve_codes mehanizam) — netaknuto, fix radi SA
  postojećom logikom, ne mijenja je.
- `gui/tabs/zaglavlje_view.py` (`_PRESERVE_REFS`, `_populate_attached_table`,
  `set_data`/`get_data`) — netaknuto (Faza 1-3 fix ostaje važeći).
- `gui/tabs/lazy_tab.py` — netaknuto. Primijećena potencijalna nuspojava
  `LazyTab.__getattr__` (vraća `_noop` umjesto bacanja `AttributeError`,
  pa `getattr(zaglavlje_tab, "service", None) or ZaglavljeService()` na
  liniji ~2304 teoretski može dobiti `_noop` ako tab nije inicijalizovan) —
  PRE-POSTOJEĆE, izvan scope-a, dokumentovano u memoriji za buduću pažnju.
- Necommitovane izmjene u `AGENTS.md`, `CLAUDE.md`,
  `agent_reports/2026-06-14_univerzalni-agent-md-template.md` (pre-postojeći
  WIP) — netaknuto, nije dio ovog commit-a.
- `client.log.lck` (untracked runtime artefakt) — netaknuto.

## Verifikacija
- `python -m py_compile gui/tabs/naimenovanja_view.py
  dist_client/gui/tabs/naimenovanja_view.py` → OK.
- Privremena dijagnostička skripta (`tmp_diag_zaglavlje.py`, obrisana nakon
  verifikacije) simulirala je CIJELI novi flow na `02.xml`:
  `parse_naimenovanja_from_xml` → `global_docs` (FIX 1) →
  `draft.header_attached_documents = global_docs` →
  `load_from_xml` → Rb.18/21 preservation + non-DIS clear →
  `save_to_draft(draft, data)` → `load_from_draft(draft)` (simulira tab
  switch reload).
  - **Izvoznik/Primalac**: `izvoznik_naziv='BIG BULL FOODS'`,
    `primalac_id='401219270002'`, `primalac_naziv='LEBURIĆ KOMERC DOO'` —
    popunjeni u `draft` i u `reload_data`. ✅
  - **Rb.18/21**: `transport_id`/`aktivno_transport`/`aktivno_transport_nat`
    postavljeni na testne vrijednosti PRIJE importa, ostaju NEPROMIJENJENI
    kroz `save_to_draft` i `load_from_draft`. ✅
  - **Rub.40**: `reload_data['attached_documents']` =
    ZUT(""), OST(""), DIS("D-222/17"), DV1(""), FTAP(""), N380(""),
    PZT(""), N730("") — SAMO DIS ima referencu. ✅
- `gitnexus_detect_changes(scope="unstaged")` → `risk_level: low`,
  `affected_processes: []`.

## Pronađeni problemi
- Nema novih problema uvedenih ovim fixom.
- Pre-postojeći (van scope-a, dokumentovan u memoriji): `LazyTab.__getattr__`
  vraća `_noop` (truthy funkciju) za nepostojeće atribute umjesto da baci
  `AttributeError` — `getattr(zaglavlje_tab, "service", None) or
  ZaglavljeService()` (linija ~2304, NEPROMIJENJENA ovom izmjenom) bi
  teoretski mogao dobiti `_noop` umjesto `None`/fallback ako Zaglavlje tab
  NIKAD nije bio prikazan prije uvoza XML-a. Nije reprodukovano u stvarnoj
  app (Zaglavlje je obično prvi/eager tab), ali ostaje kao mogući budući bug
  ako se redoslijed inicijalizacije tabova promijeni.

## Konflikti / kontradiktorni izvori
- [2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md](2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md)
  (Faza 1-3) je tvrdio da je Rub.40 čišćenje ZAVRŠENO i da `_PRESERVE_REFS`
  ostaje netaknut. Ovaj izvještaj POTVRĐUJE da `_PRESERVE_REFS` zaista
  ostaje netaknut (nije mijenjan), ali DOPUNJUJE da samo čišćenje
  `data['attached_documents']` u `_apply_xml_import_to_zaglavlje` NIJE bilo
  dovoljno zbog `global_docs`→`preserve_codes` i object-identity problema
  opisanih gore. Tretiran kao DOPUNA (ne zamjena) — nije potrebna korisnička
  potvrda za ovaj konflikt, oba izvještaja ostaju važeća zajedno.

## Commitovi
| Hash | Poruka |
|------|--------|
| `1287bd6` | `fix(naimenovanja): popuni Izvoznika/Primaoca i ocisti Rub.40 reference pri uvozu XML` |

## Rizici / ograničenja
- Ako `data['attached_documents']` (iz `load_from_xml`, header Rub.40 lista)
  NE sadrži šifru koja JE bila u `global_docs` (items' attached_documents) i
  KOJA NIJE u `preserve_codes` (npr. CMR, FAK, SAN, VET, UVK u test-XML-u) —
  ta šifra se NEĆE prikazati u Rub.40 tabeli nakon uvoza (ranije se,
  preko stare/loše putanje, prikazivala sa punom referencom). Procijenjeno
  kao ŽELJENO ponašanje (Rub.40 = deklaracijski nivo, ne item-nivo Rb.44),
  ali nije bilo eksplicitno postavljeno pitanje korisniku za OVU specifičnu
  nuspojavu.
- Fix se oslanja na `service.save_to_draft` i `zaglavlje_tab.load_from_draft`
  postojeću logiku (preserve_codes, template merge u `load_from_draft`) —
  ako se ta logika promijeni u budućnosti, ponovo provjeriti ovaj flow.

## Potreban follow-up
- Nema poznatog tehničkog follow-upa. Korisnik treba ponovo testirati uvoz
  ASYCUDA XML-a na stvarnoj aplikaciji i potvrditi da: (a) Izvoznik/Uvoznik i
  ostala polja "druge kolone" Zaglavlja sada jesu popunjeni, (b) Rub.40
  referenca prazna za sve osim DIS, (c) Rb.18/21 (prevoz) NISU promijenjeni
  uvozom.

## Potrebna korisnička potvrda
U pokrenutoj aplikaciji: Naimenovanja tab → "Uvezi ASYCUDA XML" → izabrati
XML → otvoriti Zaglavlje tab i provjeriti:
- Izvoznik (Rb.2), Primalac/Uvoznik (Rb.8) i ostala "druga kolona" polja su
  popunjena iz XML-a.
- Rub.40 (Priloženi dokumenti): referenca (3. kolona) prazna za sve šifre
  osim DIS (koja sadrži broj dispozicije).
- Rb.18/21 (prevoz) NISU promijenjeni uvozom (zadržali su prethodnu
  vrijednost ili su prazni kao i prije).
- Ako su neke šifre (npr. CMR/FAK/SAN/VET/UVK ili slično iz item-nivoa)
  potpuno NESTALE iz Rub.40 tabele — provjeriti je li to prihvatljivo ili
  treba dodatnu izmjenu (vidi "Rizici / ograničenja").
