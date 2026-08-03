# Naimenovanja 3-layer refaktor — status i nastavak (handoff za novu sesiju)

## Cilj ove sesije (kad se otvori)

Utvrditi da li je Naimenovanja tab troslojni (View/Controller/Service) refaktor
STVARNO završen, i ako nije — dovršiti ga po istom standardu koji je upravo
primijenjen na Faktura tab (vidi §6 "Referenca" ispod). Ovo NIJE nova
implementacija od nule — Controller sloj već postoji i sadrži stvarnu
orkestraciju; posao je **provjera i eventualno zatvaranje**, ne pisanje.

## 1. Poznato stanje (provjereno u kodu, ne procjena)

| Fajl | Linija | Zadnja izmjena na `windows` |
|---|---|---|
| `gui/tabs/naimenovanja_view.py` | 3236 | 2026-07-28 |
| `gui/tabs/naimenovanja_controller.py` | 313 | 2026-07-28 |
| `gui/tabs/naimenovanja_tab.py` | 100 | 2026-07-28 |
| `gui/tabs/naimenovanja_view_phase4.py` | 43 | 2026-07-28 (dodatni fajl, nema ekvivalent kod Fakture) |

- **Controller postoji i nije skelet** — 313 linija stvarne orkestracije
  (`save_current_item`, `on_tariff_changed`, `import_xml`,
  `accept_tariff_suggestion`, `update_knowledge_base`), razvijan kroz
  komitovane faze na `windows`:
  ```
  e1660da refactor(naimenovanja): Faza 1 — uvedi controller composition root bez promjene toka
  b88d509 refactor(naimenovanja): Faza 4 — Controller save/navigation metode
  41f9fb0 refactor(naimenovanja): Faza 5 — Controller tarifni tok metode
  046086f refactor(naimenovanja): Faze 6+7 — Controller dokumenti, XML, prijedlozi
  2e145c3 fix(naimenovanja): zatvori controller wiring i zastiti draft
  7d9d6e2 refactor(naimenovanja): zavrsi tarifni dokument i xml tok   (2026-07-28 07:14, Codex)
  ```
  Zadnji commit je Codex-ov, poruka "zavrsi" — to je NJEGOVA tvrdnja o
  završetku te podcjeline (tarifni dokument + XML tok), nije nezavisno
  provjerena — isti obrazac kao "Codex kaže 65%" ranije u ovoj sesiji, gdje
  se ispostavilo da tvrdnja treba provjeru, ne slijepo prihvatanje.
- **View ne poznaje Controller direktno** (0 pojava `self.controller` u
  `naimenovanja_view.py`) — komunikacija isključivo signalima, ispravan
  smjer zavisnosti.
- `docs/context/history.md` zapis #82 (2026-07-28) potvrđuje: "Promjena
  tarife kroz Naimenovanja tab prolazi View signal → Controller →
  NaimenovanjaService."
- **View ima 16 `from services.` importa.** Ovo SAMO PO SEBI nije dokaz
  problema — Faktura View ima 96 istih importa i to je ustanovljeno kao
  legitimno KAD su to pozivi na statične/bezstanjne servisne metode (npr.
  `ExportService.find_unassigned_items()` iz ove sesije). **Nije provjereno**
  da li je svih 16 poziva u Naimenovanja View-u te vrste, ili neki zaobilaze
  Controller-ov posjedovani servis (prava arhitektonska greška, isti tip
  bug-a koji je Faza 3 Faktura refaktora rješavala). **Prvi konkretan korak
  sledeće sesije.**
- **Poslije 28. jula nema nikakve dalje aktivnosti** na ovom tabu — dok je
  Faktura refaktor nastavljen do 2026-08-03 (Faza 7 + dodatni bugfix-evi).
  Ne postoji zatvarajući `agent_report` ni "ZATVARANJE" sekcija u planu za
  Naimenovanja, kakav sada postoji za Fakturu.
- **Nema izgubljenog koda.** Grana `refactor/naimenovanja-3layer` postoji,
  nije spojena u `windows`, ali sadrži samo 1 commit koji `windows` nema
  (`8c754c5`, dokumentacioni, o Faktura planu — ne Naimenovanja kod).
  Nekomitovane izmjene u tom worktree-u su isključivo Qt-generisani UI
  fajlovi (verzija/geometrija drift, poznat bezopasan obrazac — vidi
  `project_rooms/2026-07-23_nalazi-duboke-istrage.md:169`).

## 2. Ključan nalaz: plan dokument NIJE izgubljen, samo je na drugoj grani

`project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md`
(801 linija, autor Codex, datum 2026-07-27) **postoji**, ali je commitovan
SAMO na grani `feature/agent-v2` (commit `f561e55`), nikad spojen u
`windows`. Sam refaktor KOD je poslije prenesen na `windows` (faze
navedene gore), ali plan-dokument koji ga je vodio nije prenesen zajedno
s njim.

**Pročitati prije bilo čega drugog u sledećoj sesiji:**
```bash
git show f561e55:project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md
```
Sadrži (viđeno u prvih 40 linija): cilj refaktora, obaveznu strategiju
grane/worktree-a, kriterijume "View nema DB pristup ni poslovne odluke",
"Controller orkestrira ali ne implementira carinska pravila", itd. — vjerovatno
i originalnu fazu-po-fazu podjelu koju su Faza 1/4/5/6+7 commiti pratili.

Prethodnik `project_rooms/2026-07-26_naimenovanja-3layer-refaktor-plan.md`
nikad nije commitovan nigdje (0 rezultata u `git log --all`) — vjerovatno
radni nacrt koji je zamijenjen 07-27 verzijom prije prvog commit-a.

## 3. Plan za sledeću sesiju (predlog, ne obaveza — prilagoditi po nalazu)

1. **Pročitati** `f561e55:project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md`
   u cijelosti — to je autoritativni kriterijum "šta znači završeno" za ovaj
   tab, napisan PRIJE nego je rad počeo.
2. **Uporediti kriterijume iz plana sa stvarnim stanjem koda** — isto kao
   što je urađeno za Fakturu (grep provjere, ne pretpostavke).
3. **Provjeriti prirodu 16 `from services.` importa** u `naimenovanja_view.py`
   — legitimni statični pozivi vs. Controller-bypass (vidi §1 gore).
4. **Audit `_on_*`/business-logic-bearing metoda** u `naimenovanja_view.py`
   (3236 linija — provjeriti da li poslovna logika još curi u Qt handlere),
   isti obrazac kao Faktura Faza 7 audit — vidi
   `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` sekcija
   "FAZA 7" za tačan metod klasifikacije (čist wiring / mješovito-trivijalno /
   sadrži logiku / visok rizik).
5. **GitNexus impact provjera** prije bilo koje izmjene (obavezno po
   AGENTS.md/CLAUDE.md).
6. Ako se otkrije da nešto stvarno nedostaje: popraviti test-first
   (karakteristični test prije izmjene), sync `dist_client/`, GitNexus
   `detect_changes`, commit.
7. Ako se potvrdi da je stvarno završeno: napisati zatvarajući `agent_report`
   + "ZATVARANJE" sekciju u ovom project_room-u (isti format kao
   `agent_reports/2026-08-02_faktura-3layer-faza7-zatvaranje.md`), da
   Naimenovanja ima isti nivo dokumentovane pouzdanosti kao Faktura sad ima.

## 4. Šta NE dirati / ne miješati

- **Parser Studio** (`C:\Users\38765\Desktop\parser_studio\`) — potpuno
  odvojen projekat (poseban git repo), nema veze sa `deklarant_pro` kodom.
  Trenutno stanje: F0 (skelet, vendorovan ugovor, ExcelDocument,
  excel_headers engine) urađeno, ali **plan je promijenjen nakon razgovora
  o domenu** (odbačen wizard-pristup, usvojen "jedan generički prepoznavač
  bez ručnog mapiranja po dobavljaču") — vidi
  `C:\Users\38765\Desktop\parser_studio\PLAN.md` (v2). Korisnik čeka drugo
  mišljenje (ChatGPT) prije nastavka koda. Ne nastavljati Parser Studio kod
  u ovoj (Naimenovanja) sesiji osim ako korisnik eksplicitno to zatraži.
- `AGENTS.md`, `CLAUDE.md`, `dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`,
  `dist_client/ui/zaglavlje_tab_ui.py` — zatečeni nekomitovan WIP drugog
  agenta/sesije (viđeno u `git status --short` na početku ove sesije i i
  dalje prisutno na kraju) — ne dirati, ne komitovati kao svoje.
- Faktura tab je **potpuno zatvoren** ove sesije (Faza 1-7 + 2 bugfixa +
  bojenje-po-grupi feature) — ne treba dalji rad osim ako korisnik nešto
  novo primijeti kroz GUI testiranje.

## ZATVARANJE (djelimično) — nalaz sesije 2026-08-03 druga polovina

**Status: NIJE završeno.** Provjera §3 tačaka 1-4 urađena (plan pročitan,
16 `from services.` importa u `naimenovanja_view.py` pojedinačno
klasifikovano, `_on_*` handleri audit-ovani). Rezultat: Controller sloj je
stvarno ispravan za dio tokova (save/navigacija, tarifna promjena, PE sync,
XML import entry point, tarifni prijedlozi), ali **4 toka i dalje potpuno
ili djelimično zaobilaze Controller**:

1. **`_add_history_docs`** — **RIJEŠENO ovom sesijom** (commit `6b20f57`).
   Nakon provjere: metoda nije bila živi bug nego mrtav kod — nikad
   pozivana na `windows` (0 poziva u cijelom repou van worktree-ova),
   superseded ispravnim tokom `NaimenovanjaController.on_tariff_changed`
   → `NaimenovanjaService.add_tariff_documents(draft, tariff_code)`
   (`services/naimenovanja/naimenovanja_service.py:467`), koji radi isti
   posao i više (dodaje i `get_required_docs` po tarifnom pravilu, ne samo
   istoriju). Obrisana u `gui/tabs/naimenovanja_view.py` i
   `dist_client/gui/tabs/naimenovanja_view.py`. py_compile OK, puna
   `pytest tests/ -q` 1684 passed (4 pre-postojeća fail-a nepovezana:
   agent tool schema, XML parser hardkodovana putanja, tarifni mapping DB
   stanje — vidi [[2026-08-01_product-tariff-mapping-word-overlap-mina-bug]]).
   Napomena: GitNexus `detect_changes` (čak i poslije `npx gitnexus analyze`)
   NIJE prikazao ovu izmjenu u `changed_symbols` — čisto brisanje metode bez
   dodirivanja susjednih linija izgleda da promakne diff-hunk mapperu; ne
   blokira jer je nezavisna provjera (grep cijelog repoa + testovi) jača.

2. **`_add_history_docs` implikacija — provjeriti i `_ask_update_knowledge_base`
   i `_auto_populate_supplementary_unit`** nisu dio ovog nalaza, nisu
   provjereni ovom sesijom — ostaju otvoreni za sledeću turu istog audit-a.

3. **`_apply_xml_import_to_zaglavlje`** (`naimenovanja_view.py:2036`,
   NIJE popravljeno) — View instancira `ZaglavljeService()` direktno, radi
   `self.draft = service.save_to_draft(...)`, bez Controllera. Faza 7 plana
   eksplicitno predviđa ovo kao Controller-orkestrisan tok. Ostaje follow-up.

4. **`_on_save`** (`naimenovanja_view.py:2317`, NIJE popravljeno) — cio
   izvoz deklaracije (file dialog + `DeclarationDraftService`) živi u
   View-u bez signala ka Controlleru. Plan §7.2 eksplicitno navodi
   `_on_save` kao metodu koja "prelazi u Controller". Ostaje follow-up.

5. **`_setup_package_dropdown` / `_setup_rb40_widgets`**
   (`naimenovanja_view.py:836, 1069`, NIJE popravljeno) — View sam
   instancira `NaimenovanjaService()` za DB-backed šifarnike umjesto da ih
   dobije od Controllera. Faza 3 gate ("Service vraća kataloge; View samo
   puni widgete") nije ispunjen za ove setup metode. Ostaje follow-up.

**Korisnička odluka (upitano putem AskUserQuestion)**: od ponuđenih opcija
(pun nastavak Faza 6+7 odjednom / samo dokumentuj bez diranja koda / uzak
fix najrizičnijeg nalaza) korisnik je prvo izabrao **uzak fix najrizičnijeg
nalaza** — što se pri provjeri pokazalo kao čisto brisanje mrtvog koda, ne
kao migracija žive poslovne logike.

## ZATVARANJE (konačno) — nastavak iste sesije, korisnik je zatražio "popravi sve"

Korisnik je potom eksplicitno zatražio da se preostale 3 stavke isto
riješe ("popravi sve"). Rezultat nakon istrage i implementacije:

3. **`_apply_xml_import_to_zaglavlje`** — **RIJEŠENO** (commit `3625286`),
   ali NE migracijom nego istim nalazom kao `_add_history_docs`: metoda je
   bila **mrtav kod**, nikad pozivana na `windows` (0 poziva repo-wide grep-om
   van starih worktree-ova `agent-v2`/`codex-faktura-toolbar`). Superseded
   je ispravnim `NaimenovanjaService.import_xml()`
   (`services/naimenovanja/naimenovanja_service.py:608`), koji Controller
   već poziva preko `import_xml_requested` signala i koji radi isti posao
   (transport_id/aktivno_transport zadržavanje, Rb.40 DIS-only referenca) i
   više (PE1/PE2/PE3 master_pe distribucija na iteme, `items` assignment) —
   sve u jednoj koherentnoj draft mutaciji umjesto dva odvojena side-effecta
   kakva je stari View metod imao. Obrisana u oba fajla (`gui/`,
   `dist_client/`).

4. **`_on_save`** — **RIJEŠENO** (commit `3625286`), ovaj put stvarnom
   migracijom (metoda je bila živa — vezana na `btn_sacuvaj.clicked` i
   `Ctrl+S`). Novi `NaimenovanjaController.save_declaration(view, filename)`
   radi: `save_current_item` → `save_header_fn()` callback → `DeclarationDraftService().save()`
   → `draft._persistent_draft_path`/`draft.dirty` → `view.show_success/show_error`.
   View sad samo bira fajl (file dialog, `suggested_filename`/
   `default_drafts_directory` kao read-only helperi) i emituje
   `save_declaration_requested(str)`. Usput otkrivena i popravljena ista
   klasa problema u susjednoj grani koda: `is_draft_file` grana unutar
   `_on_import_xml` (otvaranje POSTOJEĆEG nacrta, ne uvoz naimenovanja) je
   isto direktno pozivala `DeclarationDraftService().load()` i
   `main_window._replace_draft_contents()`/`_reload_all_tabs_from_draft()`
   bez Controllera — nije bila u originalnoj listi od 3, ali je ista
   arhitektonska greška u istom servisu, pa je migrirana istom prilikom u
   novi `Controller.load_declaration(view, filename)`. Oba nova Controller
   metoda koriste `save_header_fn`/`replace_draft_fn` callback-ove ožičene
   u `NaimenovanjaTab` (`_save_header`, `_replace_draft`) — isti obrazac
   kao postojeći `reload_header_fn`/`_reload_header`.

5. **`_setup_package_dropdown` / `_setup_rb40_widgets`** — **RE-KLASIFIKOVANO,
   NIJE gap**. Ponovna analiza istim standardom kao `_add_history_docs`:
   ovo su čisto read-only katalog lookupi (`load_package_codes()`,
   `load_previous_documents()`) bez draft mutacije i bez poslovne odluke —
   isti prihvaćeni obrazac kao 96 direktnih service importa u Faktura View-u
   i tarifni opis-lookupovi u ovom istom View-u. Dodatno: `NaimenovanjaView`
   se konstruiše PRIJE `NaimenovanjaController`-a u `NaimenovanjaTab.__init__`
   (`self.view = NaimenovanjaView(...)` pa tek onda `self.controller = ...`),
   pa bi "premještanje u Controller" zahtijevalo reorganizaciju composition
   roota za nultu stvarnu korist (nema šta da se zaštiti od draft mutacije).
   GitNexus impact: LOW, jedini pozivalac `__init__` (potvrđuje da su
   isključivo dio jednokratnog UI setupa, ne runtime data-flow-a). Namjerno
   ostavljeno netaknuto.

**Karakterizacioni test prije implementacije**: `tests/unit/
test_naimenovanja_controller_declaration_save_load.py` (4 testa, stvaran
`DeclarationDraftService` round-trip na `tmp_path`, bez mock-ovanja —
pokriva save uspjeh/neuspjeh i load uspjeh/neuspjeh preko fake `view`-a).

**Status: ZAVRŠENO.** Svih 5 originalno identifikovanih stavki riješeno:
1 riješena ranije u sesiji (`_add_history_docs`, dead code), 2 riješene u
ovom nastavku (`_apply_xml_import_to_zaglavlje` dead code,
`_on_save`+`is_draft_file` grana stvarna migracija), 1 dodatno pronađena i
riješena usput (`is_draft_file` grana), 1 re-klasifikovana kao ne-gap
(dropdown/rb40 setup). Puna `pytest tests/ -q` (isključujući DB-zavisne
testove koji su padali zbog nedostupnog `dmserver` u trenutku ove sesije,
nepovezano sa izmjenom): identičan baseline kao prije izmjene (3
pre-postojeća fail-a + 1 error, svi nepovezani). GitNexus `detect_changes`
poslije reindexa ispravno prikazuje scope izmjene (10 fajlova, risk_level
low, affected_processes prazno).

Preostao rad na Naimenovanja tabu (van scope-a ove sesije, nije "gap" nego
generalni dug): nema karakterizacionih testova za `naimenovanja_view.py`
u cjelini (Faza 0 plana nikad urađena na `windows`) — svaka buduća izmjena
preostalih View metoda i dalje nosi veći rizik regresije bez njih. Ovo NIJE
hitno jer trenutno ponašanje taba nije promijenjeno ovom sesijom.

## 5. Referenca — kako je Faktura zatvorena (isti standard za primijeniti ovdje)

- `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` — puna
  istorija svih faza, uklj. "ZATVARANJE" sekciju na kraju (format za
  kopiranje).
- `agent_reports/2026-08-02_faktura-3layer-faza7-zatvaranje.md`,
  `agent_reports/2026-08-02_faza7c-offscreen-provjera-i-kriticni-bug.md` —
  primjeri zatvarajućih izvještaja, uklj. offscreen-test metodologiju koja je
  uhvatila pravi bug (`auto_applied` nikad nije upisivao u draft) koji
  mock-testovi nisu mogli uhvatiti — vrijedi primijeniti isti pristup ako se
  za Naimenovanja nađe slična sumnjiva logika.
- Metodološka pouka iz cijele sesije: **ne vjerovati samoprijavljenom
  "gotovo"** (ni Codex-ovom, ni bilo čijem) bez nezavisne provjere —
  brojevima linija, grep-om, testovima, ili GUI potvrdom, zavisno šta je
  najjači dostupan dokaz za tip tvrdnje.
