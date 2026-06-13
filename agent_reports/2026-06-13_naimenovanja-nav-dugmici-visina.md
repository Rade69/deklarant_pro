# Naimenovanja: nav dugmici nemaju vidljiv donji rub (preklapanje sa trakom ispod)

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `styles/naimenovanja_components.qss` + `dist_client/styles/naimenovanja_components.qss` — jedino izmijenjeni fajlovi (CSS-only fix)

## GitNexus impact
QSS fajlovi nisu indeksirani kao simboli (CSS, ne kod) - `gitnexus_impact`
nije primjenjiv. `gitnexus_detect_changes(scope="unstaged")` prije commita:
`risk_level: "low"`, `affected_processes: []` - sve prijavljene promjene
odnose se na PRETHODNI nepovezan WIP (`apply_display_profile` u
`faktura_view.py`, gui+dist_client), ne na ovaj fix.

## Šta je urađeno
Dodat ciljani QSS override `QWidget#navBar QPushButton { min-height: 16px;
padding: 4px 12px; }` odmah iza postojećeg `QWidget#navBar {...}` bloka, u
oba stabla (`styles/` i `dist_client/styles/`).

## Zašto je urađeno
Korisnik je poslao screenshot Naimenovanja navigacione trake i pitao:
"dugmad nemaju donji dio i one se ne vidi od gornjeg djela plave trake a
trebalo bi da se vidi". Offscreen dijagnostika (`QT_QPA_PLATFORM=offscreen`,
sa svim učitanim QSS fajlovima, `tab.grab()` crop) je potvrdila: svi nav
dugmici (`btn_previous`, `btn_next`, `btn_add`, ...) imaju u kodu
`setFixedHeight(30)`, ali se REALNO renderuju na **38px**
(`minimumHeight()=38 > maximumHeight()=30` - kontradiktorno stanje).

Uzrok: globalni `QPushButton { min-height: 28px; padding: 5px 12px; border:
1px solid transparent; }` iz `QSS_header_toolbar_sistem.qss` se primjenjuje
KASNIJE (Qt `polish()` na prvi `show()`) i prepisuje `minimumSize` na ~38px,
ne dirajući `maximumSize` (30, od `setFixedHeight`). `nav_bar` ima
`setFixedHeight(38)`, a `section_heading` (tamnoplava "Naimenovanje #X"
traka) počinje TAČNO na y=38 unutar `nav_bar`-a - dugme od 38px
(pozicionirano na y=4) završava na y=42, tj. **4px UNUTAR
`section_heading`-a**. Zbog toga donji rub dugmeta (zaokruženi ugao,
border) izgleda kao da je "pojeden" tamnoplavom trakom.

## Kako je urađeno
- `QWidget#navBar QPushButton` (ID selektor + tip) ima VEĆU specifičnost od
  golog `QPushButton` u `QSS_header_toolbar_sistem.qss`, pa override
  pobjeđuje BEZ OBZIRA na redoslijed učitavanja fajlova (`naimenovanja_components.qss`
  se učitava PRIJE `QSS_header_toolbar_sistem.qss`, ali specifičnost
  nadjačava redoslijed).
- `min-height: 16px` + `padding: 4px 12px` + postojeći `border: 1px solid
  transparent` (iz globalnog pravila, nije dirano) → CSS min-height box
  ≈ 16+8+2=26px, ispod `setFixedHeight(30)`-ovog maximuma (30) → nema više
  `minimumHeight > maximumHeight` kontradikcije.
- Provjereno da postoji DRUGI `#navBar` u repou
  (`gui/components/navigation_controls.py`, klasa `NavigationControls`,
  `setFixedHeight(50)`) - ali je DEAD CODE (grep: nigdje instanciran osim
  definicije + re-export u `components/__init__.py`), ovaj fix ga ne
  dotiče.

## Šta nije dirano
- `gui/tabs/naimenovanja_view.py` - `setFixedHeight(30)` pozivi na dugmiće
  OSTAJU (sada su konzistentni sa CSS min/max, nije bilo potrebe mijenjati
  Python kod).
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py` -
  postojeći nekomitovani WIP (`apply_display_profile`, Bruto/Neto label
  sizing preko `QFontMetrics`) - nepovezan, ostavljen netaknut i unstaged.
- `gui/components/navigation_controls.py` - dead code `#navBar` (50px),
  nije instanciran, nije dirano.

## Verifikacija
Offscreen (`QT_QPA_PLATFORM=offscreen`, sa svim 11 učitanih QSS fajlova,
`NaimenovanjaTab(draft=DeclarationDraft())`, `tab.grab()` crop):

| | Prije fixa | Posle fixa |
|---|---|---|
| `btn_previous.minimumHeight()` | 38 | 24 |
| `btn_previous.maximumHeight()` | 30 | 30 |
| `btn_previous.sizeHint()` | (135, 40) | (135, 26) |
| `btn_previous geometry` | (536, 4, 135, **38**) | (536, 4, 135, **30**) |
| `nav_bar height` | 38 | 38 |
| `section_heading geometry` | (0, 38, 1507, 30) | (0, 38, 1507, 30) |
| Preklapanje sa `section_heading` | **4px preklop** (42 > 38) | **4px razmak** (34 < 38) |

Vizuelni crop (`tab.grab()`) prije/posle potvrđuje: dugmići "PRETHODNO" /
"SLJEDEĆE" / "DODAJ" sada imaju vidljiv donji rub i razmak od tamnoplave
"NAIMENOVANJE #1" trake ispod.

## Pronađeni problemi
Nema - dijagnoza i fix su se poklopili na prvi pokušaj (geometrija prije
fixa egzaktno objašnjava prijavljeni vizuelni bug).

## Commitovi
| Hash | Poruka |
|------|--------|
| `511cc05` | `fix(gui): popravi visinu nav dugmica u Naimenovanjima (preklapanje sa trakom ispod)` |

## Rizici / ograničenja
- Override je generičan za SVE `QPushButton` unutar `#navBar` - ako se u
  budućnosti dodaju dugmići kojima treba VEĆI `min-height`/`padding`, ovaj
  override bi ih ograničio. Trenutno svi nav dugmici koriste isti
  `setFixedHeight(30)`, pa nije problem.

## Potreban follow-up
- Nema poznatih otvorenih stavki za ovaj zadatak.

## Potrebna korisnička potvrda
- Vizuelni izgled na stvarnom ekranu: dugmići "Prethodno/Sljedeće/Dodaj/
  Obriši/Sugeriši tarifu/Uvezi XML/Inspekcije" treba da imaju vidljiv donji
  rub/zaokruženi ugao, odvojen od tamnoplave "Naimenovanje #X" trake ispod.
