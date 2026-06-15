# Naimenovanja: uvoz ASYCUDA XML popunjava i Zaglavlje (Rub.40)

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/naimenovanja_view.py`
- `dist_client/gui/tabs/naimenovanja_view.py`

Read-only (samo provjera, bez izmjena):
- `services/zaglavlje_service.py`
- `gui/tabs/zaglavlje_view.py`
- `gui/tabs/zaglavlje_controller.py`
- `gui/tabs/zaglavlje_tab.py`
- `core/draft/draft.py`

## Status izvora
- Polazna tačka: prethodna sesija je već implementirala novu metodu
  `_apply_xml_import_to_zaglavlje` + pozivanje iz `_on_import_xml` u oba
  fajla, ali nije commitovala (plan je bio partial-patch odvajanje od
  Codex-ovog necommitovanog WIP-a u istim fajlovima — "Sačuvaj kao nacrt"
  funkcionalnost).
- U toku ove sesije, prije nego što je partial-patch izvršen, provjera
  `git log`/`git status` je pokazala da je **stanje već promijenjeno izvan
  ove konverzacije**: korisnik je u međuvremenu commitovao SVE zajedno
  (commit `d1fedec feat(nacrti): sačuvaj deklaraciju kao prenosivi XML`,
  Co-Authored-By: Codex) — i Codex-ov nacrt-feature i moju
  `_apply_xml_import_to_zaglavlje` izmjenu, u istom commit-u.
- Status: **aktivan, već commitovan** — partial-patch korak nije potreban
  (vidi "Konflikti" ispod).

## GitNexus impact
Prije izmjene (ranije u sesiji), provjereno `gitnexus_impact` (direction:
upstream, preko `target_uid` za `gui/` kandidate) na:
- `ZaglavljeView.set_data` → risk LOW
- `ZaglavljeView._populate_attached_table` → risk LOW
- `ZaglavljeController._on_import_xml` → risk LOW
- `NaimenovanjaView._on_import_xml` → risk LOW

`gitnexus_detect_changes(scope="unstaged")` (prije commit-a, ranije u
sesiji): `risk_level: "low"`, `affected_count: 0`, `affected_processes: []`,
`changed_count: 80`, `changed_files: 6`.

## Šta je urađeno
U `NaimenovanjaView._on_import_xml` (regularna grana, ne "Deklarant Pro
nacrt"), nakon uvoza ASYCUDA XML-a, sada se poziva nova metoda
`_apply_xml_import_to_zaglavlje(filename)` koja:
1. Učita header podatke iz istog XML-a preko
   `ZaglavljeService().load_from_xml(filename)`.
2. Ukloni iz dict-a `transport_id`, `aktivno_transport`,
   `aktivno_transport_nat` (Rb.18/21) — ova polja se NE preuzimaju.
3. Za sve stavke u `attached_documents` (Rub.40 — Priloženi dokumenti),
   isprazni `number` (referencu) za sve šifre OSIM `"DIS"`.
4. Pozove `zaglavlje_tab.view.set_data(data, _from_import=True)` i
   `zaglavlje_tab.save_to_draft()`.

Identična izmjena urađena u oba mirror-fajla (`gui/` i `dist_client/`).

## Zašto je urađeno
Korisnikov zahtjev (kroz višerundni dijalog): kad se u Naimenovanja tabu
uveze standardni ASYCUDA XML, treba se popuniti i Zaglavlje tab (konkretno
Rubrika 40 — Priloženi dokumenti, šifra+naziv), ali:
- Rb.18/21 (prevozno sredstvo) NE smije biti prepisano — prevoz nove
  deklaracije može biti drugačiji od onog u uvezenom XML-u.
- Referenca (3. kolona u Rub.40 tabeli) treba biti prazna za SVE šifre OSIM
  `DIS` (broj dispozicije), jer se nove referencе upisuju za novu
  deklaraciju. Ovo je potvrđeno preko `AskUserQuestion` (korisnikov VOZ
  primjer pokazao da i N380/OST/PE trebaju biti prazni u ovom toku — uže od
  postojećeg `_PRESERVE_REFS`).

## Kako je urađeno
- Nije reusovana teška `zaglavlje_controller._on_import_xml` pipeline
  (linije 457-578) jer ona EKSPLICITNO postavlja N380/PE/OST reference iz
  business podataka (fakture, stavke) — to bi pregazilo "samo DIS" pravilo.
- Umjesto toga, nova metoda direktno koristi `ZaglavljeService().load_from_xml()`
  (isti servis, ista `_parse_pro_xml` ruta) i radi laku pred-obradu dict-a
  PRIJE `set_data`:
  - `.pop()` za Rb.18/21 ključeve — `set_data` ne dira ključeve koji
    nedostaju u `data`, pa postojeće vrijednosti u Zaglavlju ostaju
    netaknute.
  - Ručno postavljanje `doc["number"] = ""` za sve non-DIS dokumente PRIJE
    `set_data(_from_import=True)` — `_populate_attached_table` u obje svoje
    grane (preserve/clear) tada završi s praznim `number`-om za te kodove,
    pa `ZaglavljeView._PRESERVE_REFS` NIJE trebalo mijenjati.
- Nakon `set_data`, pozvan `zaglavlje_tab.save_to_draft()` da se promjene
  upišu u `draft`.

## Šta nije dirano
- `gui/tabs/zaglavlje_view.py` (uklj. `_PRESERVE_REFS`,
  `_populate_attached_table`, `set_data`) — nepromijenjeno.
- `gui/tabs/zaglavlje_controller.py` (`_on_import_xml` i sync helperi) —
  nepromijenjeno.
- `services/zaglavlje_service.py` — nepromijenjeno.
- Codex-ov "Sačuvaj kao Deklarant Pro nacrt" feature (QSettings,
  `_on_save` rewrite, `is_draft_file` grana u `_on_import_xml`,
  `services/declaration_draft_service.py`, testovi) — nije pisan/mijenjan
  od strane ovog agenta; završen je i commitovan od strane korisnika/Codex-a
  paralelno (vidi "Konflikti").

## Verifikacija
- `python -m py_compile gui/tabs/naimenovanja_view.py
  dist_client/gui/tabs/naimenovanja_view.py` → OK (ponovo provjereno na
  kraju sesije, na već-commitovanom HEAD sadržaju).
- `gitnexus_detect_changes(scope="unstaged")` (ranije, prije commit-a) →
  `risk_level: low`, `affected_count: 0`.
- Sadržaj metode i pozivnog mjesta provjeren direktno u `git show HEAD` za
  oba fajla (`gui/` i `dist_client/`) — identičan očekivanom.

## Pronađeni problemi
- Nema novih problema u kodu. Jedini "problem" je proceduralni (vidi
  "Konflikti" ispod) — plan partial-patch odvajanja je postao bespredmetan
  jer je stanje već commitovano kombinovano, van ove konverzacije.

## Konflikti / kontradiktorni izvori
- Korisnik je u ovoj sesiji eksplicitno odabrao (AskUserQuestion): "Odvoji
  samo moju izmjenu (partial-patch)" — odvojiti `_apply_xml_import_to_zaglavlje`
  izmjenu od Codex-ovog necommitovanog WIP-a (nacrt save/load) u dva
  posebna commit-a.
- Prije izvršenja, `git log`/`git status` su pokazali da je stanje već
  promijenjeno: commit `d1fedec feat(nacrti): sačuvaj deklaraciju kao
  prenosivi XML` (Co-Authored-By: Codex) već sadrži OBA seta izmjena
  zajedno (126 linija u svakom od dva `naimenovanja_view.py`, plus
  `declaration_draft_service.py` x2 i test).
- **Tretirano kao važeće**: već-commitovano stanje (`d1fedec` +
  `c35a370`), bez daljnje git-historije izmjene (rewrite/reset bi bio
  destruktivan i nije zatražen).
- **Potrebna korisnička potvrda (DA/NE)**: NE za dalju akciju (kod je
  ispravan i commitovan), ali korisnik treba znati da njegova
  "partial-patch" odluka NIJE primijenjena — moja izmjena je ostala
  pomiješana s Codex-ovim nacrt-feature-om u `d1fedec`. Ako je razdvajanje
  i dalje bitno (npr. za code review po feature-u), bila bi potrebna
  `git rebase`/history rewrite na grani `windows`, što nosi rizik i
  zahtijeva eksplicitnu potvrdu.

## Commitovi
| Hash | Poruka | Napomena |
|------|--------|----------|
| `d1fedec` | `feat(nacrti): sačuvaj deklaraciju kao prenosivi XML` (Co-Authored-By: Codex) | Sadrži i ovu Zaglavlje-popunjavanje izmjenu (već commitovano prije ove sesije nastavka) |
| `c35a370` | `docs(report): zabilježi tok XML nacrta` (Co-Authored-By: Codex) | Agent report za nacrt-feature, nije ova izmjena |

Ova sesija nije pravila novi kod-commit (kod je već u HEAD-u). Ovaj
agent_report + memory fajl će biti commitovani kao dokumentacija.

## Rizici / ograničenja
- Nova metoda zavisi od `main_window.zaglavlje_tab` postojanja
  (`getattr(..., None)` fallback → no-op ako tab ne postoji, npr. u
  testovima/headless kontekstu) — bezbjedno, ali znači da se Zaglavlje neće
  popuniti ako se `NaimenovanjaView` koristi izolovano.
- `ZaglavljeService().load_from_xml()` greške se hvataju i loguju
  (`logger.error(..., exc_info=True)`), funkcija tiho vraća — uvoz u
  Naimenovanja NEĆE biti blokiran ako Zaglavlje-parsiranje padne, ali
  korisnik neće dobiti GUI poruku o tome (samo log).

## Potreban follow-up
- **Živo testiranje u GUI-ju** (vidi "Potrebna korisnička potvrda") —
  funkcionalnost nije testirana sa pokrenutom aplikacijom.
- Codex-ov nacrt-feature (`d1fedec`/`c35a370`) ima svoj follow-up
  (testiranje "Sačuvaj"/"Učitaj nacrt" toka) — van scope-a ovog izvještaja.

## Potrebna korisnička potvrda
U pokrenutoj aplikaciji:
1. Otvoriti Naimenovanja tab, kliknuti "Uvezi ASYCUDA XML" i izabrati
   standardni (ne-nacrt) ASYCUDA XML.
2. Provjeriti da se Zaglavlje tab popunio: Rubrika 40 (Priloženi dokumenti)
   prikazuje sve šifre+nazive iz uvezenog XML-a, ali referenca (3. kolona)
   je prazna za sve OSIM "DIS" (ako XML sadrži DIS, njegova referenca treba
   biti popunjena).
3. Provjeriti da Rb.18 (Tablica vozila) i Rb.21 (Aktivno transportno
   sredstvo + nacionalnost) NISU promijenjeni/prepisani uvozom — ostaju
   kakvi su bili prije uvoza (ili prazni ako su bili prazni).
