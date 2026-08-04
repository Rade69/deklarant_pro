## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Audit `gui/tabs/sifarnici*` (View/Controller/Service granica), analogno ranijem Zaglavlje
3-layer auditu iz iste sesije. Korisnikov zadatak: "Počni sa Sifrarnici" nakon opšteg pitanja
da li ima smisla refaktorisati Šifrarnici/Admin/Agent tabove.

## GitNexus impact
`SifarniciController` (upstream, `target_uid=Class:gui/tabs/sifarnici_controller.py:SifarniciController`):
risk **LOW**, `affected_processes: []`, `affected_modules: []`. Jedina pogođena stabla su
transitivni import-lanci (`sifarnici_tab.py` → `tab_factory.py` → `main_window.py`), bez ijedne
stvarne izvršne zavisnosti — potvrđuje da klasa nije bila dio nijednog execution flow-a.

## Šta je urađeno
1. Pročitan `gui/tabs/sifarnici_tab.py` (56 linija) — wrapper sam u komentaru priznaje da
   "Controller i Service postoje ali originalni View ih ne koristi... zadržavamo ih za backward
   compatibility".
2. Pročitan `gui/tabs/sifarnici_controller.py` (503 linije) u cijelosti — u `__init__` poziv
   `self._connect_signals()` je trajno zakomentarisan sa napomenom "Controller će se aktivirati u
   Fazi 5 kada se uspostavi pravilna MVC komunikacija — DISABLED — uzrokuje dupli event handling
   + QTreeWidget conflict". Ta faza se nikad nije desila. Metoda `_connect_signals()` (koja bi
   povezala `categories_list`, `btn_novi/uredi/obrisi/snimi`, `search_input`, `table` signale) se
   nikad ne poziva.
3. Grep za `SifarniciController\(|SifarniciService\(` kroz cio repo (van worktree-ova):
   - `SifarniciController(` — instanciran SAMO u `sifarnici_tab.py:30` (wrapper), nikad više
     referisan (`self.controller` se ne koristi ni u jednoj drugoj metodi wrappera).
   - `SifarniciService()` — instanciran na TRI mjesta: (a) `sifarnici_tab.py` (feeding u mrtvi
     Controller), (b) `sifarnici_view.py:237` — View **sam** kreira svoju Service instancu i
     poziva je direktno, zaobilazeći Controller potpuno; (c)
     `gui/tabs/agent/services/import_pipeline_service.py:661` — nezavisan potrošač iz Agent
     uvoznog pipeline-a, nepovezan sa UI tabom.
4. Grep za `self.controller` kroz `sifarnici*.py` — potvrđeno da se van konstruktora wrappera
   nigdje ne koristi.
5. Provjerene sve pozivne tačke `SifarniciTab(...)` (`tab_factory.py`) i grep za
   `sifarnici_tab.service`/`sifarnici_tab.controller` van klase — nema eksternih potrošača tih
   atributa.
6. Pročitan `gui/tabs/sifarnici/` podpaket (823 linija, 3 fajla) — potvrđeno da JESU stvarno
   korišćeni: `sifarnici_view.py` uvozi `PartnerFormStrip`, `populate_tariff_hierarchy`,
   `is_code_search`, `QuotaPanel` direktno.
7. Pročitan prethodni `agent_reports/2026-05-12_sifarnici-table-helper-refactor.md` — potvrđuje
   da je View već od maja 2026 tretiran kao rizičan monolit; prior agent je namjerno ograničio
   refaktor samo na `_create_configured_table` helper, izbjegavajući CRUD/DB/tree-view logiku.
8. Korisnik odabrao (AskUserQuestion): "Samo obriši mrtvi Controller" — najniži rizik, ne diraj
   View monolit.
9. Uklonjen `SifarniciController` uvoz i instanciranje iz `gui/tabs/sifarnici_tab.py` i
   `dist_client/gui/tabs/sifarnici_tab.py` (identična izmjena, komentar dodat objašnjavajući
   zašto Controller ne postoji). Obrisani `gui/tabs/sifarnici_controller.py` i
   `dist_client/gui/tabs/sifarnici_controller.py` (503 linije × 2).
10. `py_compile` na sva izmijenjena+povezana 4 fajla — OK.
11. `pytest tests/ -q -k "not test_db"` — 1688 passed, 3 failed (pre-postojeći, nepovezani:
    `test_tool_use.py`/`test_tool_use_offline.py` broj alata, `test_xml_parser_fix.py` hardkodovana
    Linux putanja), 3 errors (DB circuit breaker, `dmserver` nedostupan) — identičan baseline
    obrazac kao u prethodnim izvještajima ove sesije.
12. `dist_client/gui/tabs/sifarnici_tab.py` sadržajno identičan (CRLF/LF normalizovano poređenje).
13. `gitnexus_detect_changes` prije commit-a — risk low, `affected_count: 0`. Napomena: brisanje
    `sifarnici_controller.py` fajlova se NE pojavljuje u `changed_symbols` (poznat GitNexus
    kvirk — čiste brisanja se ne mapiraju pouzdano, vidi memoriju
    `feedback_gitnexus_line_shift_false_positive.md` porodicu nalaza) — nezavisno potvrđeno grepom
    da nema preostalih referenci van `.worktrees/`.
14. Provjeren `git status --short` prije staging-a — pronađen pre-postojeći nepovezan WIP
    (`AGENTS.md`, `CLAUDE.md`, `dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`,
    `dist_client/ui/zaglavlje_tab_ui.py` — bio modifikovan već na početku sesije, prije ovog
    zadatka) — NIJE staged niti commitovan (samo tačna 4 fajla su dodana eksplicitno po imenu).
15. Commit `7a900ce` — `refactor(sifarnici): ukloni mrtav SifarniciController sloj`.
16. `npx gitnexus analyze` pokrenut u pozadini nakon commita, završen uspješno (exit 0).

## Zašto je urađeno
Korisnik je ranije u sesiji izrazio želju da se smanji nepotreban kod koji ide u produkciju
("da smanjimo nepotreban kod, da ne ide u produkciju"). `SifarniciController` je bio 503 linije
koda koje se nikad ne izvršavaju — čisto uklanjanje bez ikakve promjene ponašanja aplikacije.

## Kako je urađeno
Minimalna, ciljana izmjena: uklonjen import + dvije linije instanciranja iz wrappera, obrisan
cijeli fajl Controllera (root + dist_client kopija). Nema promjene u `SifarniciView` ili
`SifarniciService` ponašanju — oba nastavljaju raditi identično kao prije (View i dalje sam
kreira i koristi svoj `SifarniciService`).

## Šta nije dirano
- `SifarniciView` (3803 linije) — ostaje monolit, i dalje sam kreira `SifarniciService` direktno
  (View→Service bez Controller posrednika i dalje postoji kao arhitektonsko odstupanje od 3-layer
  standarda, ali je FUNKCIONALAN put, ne mrtav kod — van scope-a ovog zadatka po korisnikovom
  izboru).
- `SifarniciService` (1414 linija) — nedirano, i dalje koristi View i `import_pipeline_service.py`.
- `gui/tabs/sifarnici/` podpaket (`partner_form_strip.py`, `quota_panel.py`, `tariff_hierarchy.py`)
  — potvrđeno korišćen, nedirano.
- Admin i Agent tabovi — korisnik eksplicitno rekao da se NE nastavlja na njih automatski.

## Verifikacija
`py_compile` OK. `pytest` 1688 passed / 3 pre-postojeća fail-a (nepovezano) / 3 DB errors
(nedostupan `dmserver`, nepovezano). `dist_client/` sadržajna identičnost potvrđena.
GitNexus impact LOW prije izmjene, `detect_changes` risk low poslije. Ovo je GUI izmjena bez
vizuelnog uticaja (Controller nikad nije bio na ekranu/aktivan) — nije rađen screenshot test jer
nema vidljive promjene ponašanja za provjeriti; dovoljan dokaz je import-graph + potvrda da je
`_connect_signals()` bio trajno neaktivan.

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: GitNexus impact LOW, brisanje potvrđeno kroz tri nezavisna izvora (GitNexus impact graf,
  repo-wide grep za instanciranje/upotrebu, čitanje samog `_connect_signals()` koda koji dokazuje
  namjerno onemogućavanje) — isti standard dokaza kao ranije u sesiji za slične "mrtav kod" nalaze
  (npr. Naimenovanja 3-layer audit). Nije HIGH/CRITICAL, ne dira bazu/tarifno mapiranje/XML export.

## Pronađeni problemi
`SifarniciView` direktno kreira i koristi `SifarniciService` bez Controller posrednika —
arhitektonsko odstupanje od projektnog 3-layer standarda, ali FUNKCIONALNO (ne bug). Korisnik je
eksplicitno odlučio da se za sada NE radi puni refaktor Viewa (prevelik rizik/obim za 3803-linijski
monolit, potvrđeno i ranijim agent izvještajem iz maja 2026).

## Odbačene opcije
- Pun 3-layer refaktor `SifarniciView`-a (izvući business logiku u pravi Controller/Service tok).
  Odbačeno za sada — korisnik je izabrao minimalni potez. Ako se ikad otvori: zahtijeva
  `project_room`, karakterizacione testove prije/poslije, GitNexus impact HIGH/CRITICAL provjeru
  (View ima puno direktnih pozivalaca kroz `tab_factory`/`main_window`).
- Samo dokumentovati bez brisanja koda — odbačeno, korisnik je htio stvarno smanjenje koda.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `7a900ce` | `refactor(sifarnici): ukloni mrtav SifarniciController sloj` |

## Rizici / ograničenja
Nema poznatih rizika — Controller nikad nije bio funkcionalno dostupan, pa njegovo uklanjanje ne
mijenja nijedno vidljivo ponašanje. Preostali arhitektonski dug (View→Service bez Controllera)
ostaje dokumentovan ali nedirаn.

## Potreban follow-up
Ako korisnik kasnije zatraži pun refaktor `SifarniciView`-a: koristiti isti pristup kao Faktura/
Naimenovanja/Zaglavlje 3-layer radovi ove sesije — project_room prvo, karakterizacioni testovi,
fazna migracija.

## Potrebna korisnička potvrda
Nema — audit + minimalno čišćenje je završeno onako kako je korisnik izabrao.
