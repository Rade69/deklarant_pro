# Admin tab paleta i hover

## Datum

2026-07-27

## Agent

Codex

## Scope

- `styles/admin_tab.qss`
- `dist_client/styles/admin_tab.qss`
- regresiona provjera aktivne Admin palete

## Status izvora

| Izvor | Status |
| --- | --- |
| `gui/styles/admin_tab.qss` | aktivna nova plavo-siva paleta |
| `styles/admin_tab.qss` prije izmjene | zastarjela zelena paleta |
| `dist_client/styles/admin_tab.qss` prije izmjene | zastarjela zelena paleta |
| Claudeova `AdminView._apply_styles()` izmjena | aktivna, ostavljena netaknuta |

## GitNexus impact

QSS fajlovi nisu indeksirani kao izvršni simboli. Završni
`detect_changes(all)` prijavio je LOW i 0 pogođenih procesa; izlaz je sadržao
i nepovezane izmjene drugih agenata koje nisu dio ovog zadatka.

## Šta je urađeno

- Aktivni Admin QSS prebačen je sa stare zelene na plavo-sivu paletu.
- Sidebar hover koristi `#d8e5ed` sa granicom `#b4cad8`.
- Izabrana stavka koristi primarnu `#3477a5`, hover dugmeta `#2b648c`, a
  osnovni tekst `#17324a`.
- Selektori su usklađeni sa stvarnim objectName vrijednostima:
  `AdminSidebar`, `AdminSidebarTitle`, `AdminNavigation`, `AdminContent` i
  `AdminContentStack`.
- Root i `dist_client` QSS su identični.
- Dodat je regresioni test protiv povratka stare zelene palete i gubitka
  root/dist pariteta.

## Zašto je urađeno

U projektu su postojala dva različita `admin_tab.qss` fajla. Claude je
ispravno popravio frozen putanju da `AdminView` učitava
`BUNDLE_ROOT/styles/admin_tab.qss`, ali se upravo na toj produkcijskoj putanji
nalazila stara zelena paleta sa zastarjelim selectorima `adminSidebar` i
`adminNavList`. Nova paleta je ostala u `gui/styles/admin_tab.qss` i nije bila
aktivna ni u dev ni u EXE toku.

## Kako je urađeno

Kanonski sadržaj nove palete iz `gui/styles/admin_tab.qss` preslikan je u
aktivne root i `dist_client/styles` resurse. `AdminView` Python kod i
Claudeova `get_path_settings().styles_dir` logika nisu mijenjani.

## Šta nije dirano

- Admin poslovna logika i paneli.
- Claudeova frozen resource-path izmjena.
- Globalni `unified_color_system.qss`.
- Nepovezane izmjene u `AGENTS.md`, `CLAUDE.md`, Agent widgetima i generisanim
  UI fajlovima.

## Verifikacija

- Admin QSS regresioni testovi: 2/2 prolaze.
- Admin E2E: 16/16 prolazi.
- Dodatni Admin/UI testovi: 3/3 prolaze.
- Runtime putanja potvrđena:
  `styles/admin_tab.qss`.
- Aktivni QSS sadrži novu paletu i ne sadrži stare kodove `#5a8060` i
  `#c8dcc8`.
- Puni suite: 1326 prošlo, 72 preskočena, 5 xfailed, 1 nepovezani postojeći
  pad u Pi kill-switch testu zbog `DEBUG=release`.

## Pronađeni problemi

Puni suite trenutno nije potpuno zelen jer
`tests/unit/test_penetration.py::TestKillSwitch::test_check_agent_v2_default_is_false`
učitava lokalni `DEBUG=release` kao boolean. Admin ciljane i regresione provjere
prolaze; pad nije povezan sa QSS izmjenom.

## Konflikti / kontradiktorni izvori

Naziv „nova Admin paleta“ u `gui/styles` bio je kontradiktoran stvarnoj runtime
putanji `styles`. Kao važeći izvor uzeta je plavo-siva paleta jer odgovara
trenutnim Agent konstantama i stvarnim `AdminView` objectName selektorima.
Korisnička potvrda nije potrebna za izbor jer je korisnik eksplicitno zatražio
usklađivanje sa sadašnjom paletom.

## Commitovi

Popunjava se Git historijom ovog zadatka.

## Rizici / ograničenja

Offscreen test potvrđuje učitavanje, selektore i vrijednosti boja, ali ne može
zamijeniti vizuelnu potvrdu finalnog EXE-a pri stvarnom DPI skaliranju.

## Potreban follow-up

Pri sljedećem buildu vizuelno potvrditi sidebar hover, selected stanje i
kontrast teksta.

## Potrebna korisnička potvrda

Potvrditi da Admin tab u novom EXE-u sada izgleda isto kao ostatak aplikacije.
