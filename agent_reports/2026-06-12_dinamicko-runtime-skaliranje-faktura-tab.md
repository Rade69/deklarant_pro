# Agent report — Dinamičko runtime skaliranje GUI-a (Faktura tab)

**Datum:** 2026-06-12
**Agent:** Claude Sonnet 4.6
**Scope:** `gui/utils/scaling.py` (novo), `gui/main_window.py`,
`gui/tabs/faktura_view.py`, `run.py` + identični mirror u `dist_client/`

## Šta je urađeno

- Uklonjen prethodni `QT_SCALE_FACTOR` pristup (commit c62601b) — env
  varijabla koja se postavlja samo jednom prije `QApplication` i ne može se
  promijeniti dok app radi.
- Dodat `gui/utils/scaling.py` — `ScaleManager` singleton koji dinamički,
  u toku rada, smanjuje/vraća font cijele aplikacije i registrovane fiksne
  veličine widgeta prema ekranu na kojem se prozor trenutno nalazi.
- `MainWindow` prati `windowHandle().screenChanged` i pri svakoj promjeni
  monitora poziva `_apply_scale_for_screen()`.
- `FakturaView` Bruto/Neto polja u toolbaru (sekcija "Izvezi") registrovana
  u `ScaleManager` umjesto `setFixedWidth()`.
- Sve promjene mirror-ovane identično u `dist_client/`.

## Kako je urađeno

### Arhitektura (`gui/utils/scaling.py`)
- `REFERENCE_WIDTH = 2060` — logička širina koju zahtijeva najširi toolbar
  (Faktura tab, mjereno `minimumSizeHint` ≈ 2057px).
- `MIN_SCALE = 0.6` — donja granica skaliranja (font ostaje čitljiv).
- `ScaleManager.scale_for_width(avail_width)` → `scale = avail_width / REFERENCE_WIDTH`,
  ograničeno na `[MIN_SCALE, 1.0]`.
- `ScaleManager.register_fixed_size(widget, width, height)` — pamti baznu
  (100%) veličinu i odmah primjenjuje trenutni scale.
- `ScaleManager.apply_scale(scale)`:
  1. `QApplication.setFont()` sa `pointSizeF * scale`.
  2. Ponovo primijeni `setFixedWidth/Height` na sve registrovane widgete
     (`round(base * scale)`).
  3. `_repolish_and_relayout()` (vidi ispod).

### `MainWindow` (`gui/main_window.py`, mirror u `dist_client/`)
- `ScaleManager.init(QApplication.instance())` u `__init__`.
- `showEvent()`: na prvi prikaz poveže `windowHandle().screenChanged` →
  `_apply_scale_for_screen` i odmah pozove sa trenutnim ekranom.
- `_apply_scale_for_screen(screen)`: `scale = scale_for_width(avail.width())`,
  `apply_scale(scale)`; ako `scale < 1.0` → `self.setGeometry(avail)` (popuni
  mali ekran); ako `scale == 1.0` → ostavi geometriju kakva je (vrati na 100%
  bez mijenjanja veličine prozora).

### `FakturaView` (`gui/tabs/faktura_view.py`, mirror u `dist_client/`)
- Bruto/Neto labele i input polja (`bruto_label`, `input_bruto`, `neto_label`,
  `input_neto` u "Izvezi" sekciji toolbara) — `setFixedWidth()` zamijenjen sa
  `register_fixed_size(widget, width=N)` (50/90/50/90).
- `gitnexus_impact` na `_populate_toolbar_section` prije izmjene: rizik LOW
  (3 impacted, 1 direktan caller `_populate_grid_sections`, 0 procesa).

### Ključni bug pronađen tokom verifikacije
Offscreen dijagnostika (`QT_QPA_PLATFORM=offscreen`) je pokazala da
`FakturaView.minimumSizeHint()` ostaje zaleđen na `2057x262` bez obzira na
`apply_scale()`, iako se `app.font().pointSizeF()` i registrovani widgeti
ISPRAVNO mijenjaju.

Uzrok: `QApplication.setFont()` šalje `FontChange` rekurzivno djeci
top-level widgeta i `widget.font()` se ažurira korektno — ali `QPushButton`
(i slični widgeti) **keširaju `sizeHint()`** i ne invalidiraju ga na taj
rekurzivni event (samo na direktan `ApplicationFontChange` top-level
widgetu). Rezultat: layout-i koriste STARI `sizeHint()` pa se
`minimumSizeHint()` cijelog taba nikad ne smanji.

**Fix**: `ScaleManager._repolish_and_relayout()` — za svaki widget iz
`app.allWidgets()`: `style().unpolish(w); style().polish(w)` (forsira
ponovno računanje `sizeHint()` na novom fontu) + `layout().invalidate()`,
zatim `topLevelWidgets()[*].layout().activate()`.

### Verifikacija (offscreen, FakturaView)
| Ekran (logička širina) | scale | minimumSizeHint |
|---|---|---|
| 2060px (referenca) | 1.0000 | 2057x262 |
| 1536px (laptop) | 0.7456 | 1797x262 |
| 1920px (Full HD) | 0.9320 | 1986x262 |
| 2200px (veliki monitor) | 1.0000 | 2057x262 (egzaktan povratak) |

Na 1536px ekranu toolbar i dalje ostaje malo širi (1797 vs 1536), ali je to
~260px manje "viška" nego prije (521px), i prozor se širi preko cijelog
malog ekrana (`setGeometry(avail)`) pa je squishing značajno manji. Povratak
na veliki ekran je egzaktan (1:1 sa originalnom veličinom).

## Zašto

Korisnikov zahtjev (verbatim): "kad aplikaciju prebacim na sekundarni monitor
koji 21+ inča aplikacija ostaje iste veličine kao da je na laptopu koji je
15inča" — `QT_SCALE_FACTOR` se ne može mijenjati u toku rada, pa je odbačen u
korist runtime rješenja koje reaguje na `screenChanged` (korisnikov izbor
nakon AskUserQuestion: "Dinamičko runtime skaliranje").

## Commitovi

| Hash | Poruka |
|---|---|
| `833c1f5` | feat(gui): dinamicko runtime skaliranje GUI-a prema velicini ekrana |
| `c678084` | fix(gui): registruj Bruto/Neto polja faktura taba u ScaleManager |
| `365d06e` | fix(gui): skaliraj globalni QSS proporcionalno umjesto samo app fonta |

## DOPUNA (isti dan) — fix iznad NIJE radio u stvarnoj app

Korisnik je odmah nakon prvog izvještaja poslao screenshot sa laptopa:
toolbar identično skršen kao prije fixa ("Kreiraj N...", "Validac",
"Prethodna deklaraci..." skraćeno, Bruto/Neto polja stisnuta), i korisnik
NIJE MOGAO ručno smanjiti prozor da ga prebaci na drugi monitor.

### Pravi uzrok

Offscreen verifikacija iz prvog kruga NIKAD nije učitavala globalni QSS
(`MainWindow.load_stylesheet()` — 10 fajlova). Ti QSS fajlovi
(`button_system.qss`, `unified_color_system.qss`, `QSS_header_toolbar_sistem.qss`...)
postavljaju `font-size`, `padding`, `min-width/min-height` u **apsolutnim
px/pt jedinicama** na `QPushButton.btn_*` klase. `QStyleSheetStyle` te
vrijednosti primjenjuje NEZAVISNO od `QApplication.setFont()` — font sa
pixelSize-om iz QSS-a se ne mijenja kad app font promijeni pointSize.

Mjereno SA učitanim QSS-om (isti diagnostic kao prvi put, ali sa
`app.setStyleSheet(combined_style)`):

- `minimumSizeHint` na scale=1.0 = **2247x286** (ne 2057 kao bez QSS-a).
- `apply_scale(0.7456)` (1536px ekran) ga je smanjio na samo **2211x286**
  — tek ~1.6% redukcije. Praktično bez efekta.

Isti uzrok objašnjava i "ne mogu smanjiti prozor": Qt-ov default layout size
constraint čini layout-ov `minimumSize` (≈2247px) EFEKTIVNIM minimumom
prozora, nadjačavajući `setMinimumSize(1200,700)` iz `main_window.py:37`.

### Drugi fix (commit `365d06e`)

`ScaleManager._scale_stylesheet(css, scale)` — regex preskalira SVE `px`/`pt`
vrijednosti u CIJELOM globalnom stylesheet-u proporcionalno scale faktoru
(font-size, padding, min-width/min-height, border-radius...).
`apply_scale()` čuva originalni `app.styleSheet()` (lijeno, pri prvom pozivu)
i pri svakoj promjeni scale-a re-primjenjuje preskalirani QSS +
`_repolish_and_relayout()`. `REFERENCE_WIDTH` ažuriran 2060 → **2250**
(stvarni minimumSizeHint sa QSS-om).

### Verifikacija (offscreen, SA učitanim QSS-om)

| Ekran | scale | minimumSizeHint | redukcija vs 2247 |
| --- | --- | --- | --- |
| 2250px (referenca) | 1.0000 | 2247x286 | 0% |
| 2200px | 0.9778 | 2244x288 | ~0% |
| 1920px | 0.8533 | 1986x272 | ~12% |
| 1536px (laptop) | 0.6827 | 1648x251 | ~27% |
| 1366px | 0.6071 | 1523x244 | ~32% (blizu MIN_SCALE=0.6) |

## Napomena / mogući follow-up

- Na 1536px ekranu ostaje ~112px (7%) viška (1648 vs 1536) — od layout
  spacing/margins (`toolbar_layout.setSpacing(6)`,
  `setContentsMargins(8,8,8,8)`) i qtawesome icon size-ova POSTAVLJENIH U
  PYTHON KODU, koje `_scale_stylesheet` ne dodiruje (samo QSS). Ako korisnik
  i dalje vidi squishing/truncation nakon ovog fixa, sljedeći korak je
  skalirati i te Python-side vrijednosti kroz `register_fixed_size()` ili
  analogni mehanizam.
- Efektivni minimum prozora bi trebao pasti sa ~2247px na ~1648px na malom
  ekranu — i dalje iznad `setMinimumSize(1200,700)`, ali korisnik bi sada
  trebao moći smanjiti prozor znatno više nego prije (za prebacivanje na
  drugi monitor).
- **POTREBNA POTVRDA NA STVARNOM LAPTOPU** — offscreen diagnostika ne može
  vizuelno potvrditi izgled; potrebno je da korisnik restartuje app i provjeri
  da li su dugmad/Bruto/Neto polja sada vidljiva bez skraćivanja.

## DOPUNA 2 (isti dan, commit `726b9db`) — 2 nova bug-a iz screenshot-a NAKON `365d06e`

Korisnik je poslao novi screenshot: toolbar sekcije/dugmici sada VIDNO
staju (bez mid-word skraćenja) — velika promjena nabolje. Prijavio je 2
preostala problema:

### Bug A — "Bruto:"/"Neto:" labele odsječene na "uto:"/"eto:"

`bruto_label`/`neto_label` u `gui/tabs/faktura_view.py` (i `dist_client/`
mirror) imale su `register_fixed_size(width=50)` (na scale=0.6827 →
container = 34px) KOMBINOVANO sa inline `setStyleSheet("...font-size: 14px;
font-weight: bold;")`. Inline per-widget stylesheet NIJE dio
`app.styleSheet()` pa ga `_scale_stylesheet` ne dodiruje — font ostaje
zakucan na 14px bold, dok se kontejner smanjio na 34px. "Bruto:" na 14px
bold treba ~45-50px → desno-alignovan tekst se odsijeca slijeva.

**Fix**: uklonjen `register_fixed_size()` i fiksni `font-size: 14px` (ostalo
samo `color: #222; font-weight: bold;`). `sizeHint()` sada prati skalirani
`app.font()` — labela se ne odsijeca na bilo kojem scale-u. Verifikovano
offscreen sa QSS: `fits_bruto=True`/`fits_neto=True` na 1920/1536/1366px,
minimumSizeHint @1536px = 1652px (bilo 1648, +4px negligibly).

### Bug B — nema minimize/close dugmica na malom ekranu

`_apply_scale_for_screen` je (od PRVOG fixa, `833c1f5`) pri `scale < 1.0`
zvao `self.setGeometry(avail)`. `QWidget.setGeometry()` za top-level prozor
postavlja geometriju BEZ window frame-a na `(avail.x(), avail.y())` — Qt na
Windowsu zatim crta title bar (minimize/maximize/close) IZNAD te tačke, na
negativan `y` (van vidljivog ekrana). Korisnik je ovo prijavio u OBA
screenshot-a ("I dalje" = "still") — bug postoji od prvog commit-a ove
sesije, nije novi regres.

**Fix**: `setGeometry(avail)` → `self.showMaximized()` (scale < 1.0) /
`self.showNormal()` (scale vraćen na 1.0, samo ako je maksimizacija bila
automatska — flag `self._auto_maximized`, da se ne poremeti prozor koji je
korisnik RUČNO maksimizovao). `showMaximized()` prepušta window manageru da
korektno smjesti frame unutar ekrana.

### Otvoreno pitanje — "web-like responsiveness"

Korisnik je pitao može li se primijeniti "neka vrsta responzivnosti kao kod
web aplikacija" (flex-wrap stil). Odgovoreno preporukom (Qt `QFlowLayout` za
toolbar sekcije kao analogija CSS flex-wrap) BEZ implementacije — čeka
potvrdu smjera od korisnika kao follow-up.

### Commit (dopuna 2)

| Hash | Poruka |
| --- | --- |
| `726b9db` | fix(gui): popravi minimize/close dugmice i odsjecene Bruto/Neto labele |

## DOPUNA 3 (isti dan, commits `07a6755`, `347a8de`) — FlowLayout redizajn, ScaleManager UKLONJEN

Nakon Dopune 2, korisnik je pitao može li se primijeniti "web-like
responsiveness" (flex-wrap stil) na Faktura toolbar umjesto daljeg
podešavanja `ScaleManager`-a. Korisnikova Codex-analiza je pokazala da OBA
realna ekrana (laptop 1536x816@125%, scale=0.6827; ASUS VX239 1920x1032@100%,
scale=0.8533) padaju ispod `REFERENCE_WIDTH=2250`, pa `ScaleManager` OBA
ekrana smanjuje i prisilno maksimizira — standardni 1920px monitor je
ispadao "sitan, gotovo nečitljiv" jer je već-smanjen UI razvučen preko cijelog
velikog ekrana. Korisnik je odobrio redizajn ("Hajde da vidimo kako će to
izgledati") — plan: `C:\Users\38765\.claude\plans\atomic-inventing-duckling.md`.

### Šta je urađeno (dopuna 3)

1. Novi `FlowLayout` widget — `gui/widgets/flow_layout.py` +
   `dist_client/gui/widgets/flow_layout.py` (standardni Qt "Flow Layout"
   recept portovan na PySide6).
2. Redizajn `_create_controls_section`/`_populate_grid_sections` u
   `gui/tabs/faktura_view.py` i `dist_client/gui/tabs/faktura_view.py` — 5
   toolbar sekcija postaju "kartice" (header `QPushButton` + `FlowLayout`
   toolbar), sve kartice u vanjskom `FlowLayout`-u. `_create_thick_separator`
   uklonjen iz oba fajla.
3. Potpuno uklonjen `ScaleManager` — obrisani `gui/utils/scaling.py` i
   `dist_client/gui/utils/scaling.py`; uklonjen import/init/
   `_apply_scale_for_screen`/`screenChanged`-connect iz `gui/main_window.py`
   i `dist_client/gui/main_window.py`; `register_fixed_size(...)` pozivi u
   oba `faktura_view.py` zamijenjeni sa `setFixedWidth(90)` za Bruto/Neto
   polja.

### Kako je urađeno (dopuna 3)

- **"Kartica"**: `QWidget` (objectName="toolbarCard") sa `QVBoxLayout` —
  header `QPushButton` (disabled, boja po sekciji, zaokruženi uglovi na vrhu,
  `font-size: 17px`, `padding: 10px 6px`, `setFixedHeight(40)`) + tijelo
  (`QWidget` objectName="toolbarCardBody", `WA_StyledBackground`, bijela
  pozadina, zaokruženi donji uglovi) čiji layout je
  `FlowLayout(margin=8, h_spacing=6, v_spacing=6)`. Svih 5 kartica ide u
  vanjski `FlowLayout(container, margin=0, h_spacing=12, v_spacing=12)`.
  `_populate_toolbar_section(toolbar_flow, idx)` ostaje NEPROMIJENJEN —
  `addWidget()` radi identično u `FlowLayout` kao u `QHBoxLayout`.
- `hasHeightForWidth=True` u `FlowLayout` je ključan — `QVBoxLayout` (glavni
  layout `FakturaView`) ga poštuje i automatski daje containeru više visine
  kad se širina smanji i kartice se prelome u više redova.
- **ScaleManager uklanjanje**: grep potvrdio NULA referenci na
  `ScaleManager`/`register_fixed_size`/`gui.utils.scaling` u cijelom repou
  nakon brisanja.
- Redizajn je prirodno otklonio pred-postojeću razliku gui/ vs dist_client/
  (header height=40/font=17px vs 30/14px) — oba sada koriste isti novi stil.
- `gitnexus_impact` provjeren za sve mijenjane simbole — svi LOW risk.
  `gitnexus_detect_changes(scope="staged")` za commit `347a8de`: risk_level
  "low", 31 promijenjenih simbola, 4 fajla, 0 affected_processes.
- Partial-patch staging (kao u `726b9db`) korišten da se NE dirne pred-postojeći
  unstaged WIP u oba `faktura_view.py` fajla (validation-issue-counts feature
  i nezavisni Blagic Attos dedup WIP) — `git diff HEAD -- <file> | head -N`,
  `git apply --cached --check`, `git apply --cached`.

### Verifikacija (offscreen, SA učitanim pravim QSS-om)

| Mjera | Prije | Posle |
| --- | --- | --- |
| `controlsContainer.minimumSizeHint()` | 2247x286 | 260x128 |
| `view.minimumSizeHint()` | 2247x286 | 1358x286 |

Broj redova kartica prema širini containera:

| Širina | Redovi kartica |
| --- | --- |
| ≥1200px | 1 |
| 1000px | 2 |
| 700px | 2 |
| 500px | 3 |

Bez Python exception-a pri konstrukciji/resize-u.

## Zašto (dopuna 3)

Sa `FlowLayout` toolbar adaptira širinu na BILO KOJOJ veličini ekrana
prelamanjem kartica u redove — globalno smanjivanje fonta/QSS-a
(`ScaleManager`) više nije potrebno niti poželjno, jer je upravo ono
uzrokovalo da standardni 1920px monitor izgleda "sitan". Prozor ostaje
slobodno smanjiv do `setMinimumSize(1200,700)` bez ikakvog auto-maximize-a.

## Napomena / preostalo

- **POTREBNA VIZUELNA POTVRDA NA STVARNOM HARDVERU** (oba monitora — laptop
  1536x816@125% i ASUS VX239 1920x1032@100%) — offscreen verifikacija
  potvrđuje samo geometriju/prelamanje, ne boje/razmake.
- Ako se ista "sitan UI na velikom monitoru" pojava primijeti na drugim
  tabovima (Naimenovanja/Zaglavlje/Šifrarnici), isti FlowLayout "kartica"
  pattern je direktno prenosiv (pomenuto u memory fajlu).

### Commitovi (dopuna 3)

| Hash | Poruka |
| --- | --- |
| `07a6755` | feat(gui): dodaj FlowLayout widget za responzivni toolbar |
| `347a8de` | refactor(gui): Faktura toolbar koristi FlowLayout, ukloni ScaleManager auto-skaliranje |

## DOPUNA 4 (isti dan, commit `6788444`) — REZULTAT: korisnik odbio FlowLayout, sve vraćeno na original

Korisnik je testirao FlowLayout redizajn na stvarnom hardveru (laptop +
ASUS VX239 monitor) i odgovorio: **"Potpuni debakl ideje, vrati sve na
staro oboje užasno"** — redizajn odbijen na OBA ekrana, bez detalja šta
konkretno nije valjalo (boje/razmaci/veličine).

Na pitanje koje "staro" stanje vratiti, korisnik je izabrao **najradikalniju
opciju**: revert SVIH commit-a iz cijele sesije skaliranja (`c62601b` do
`347a8de` — QT_SCALE_FACTOR, ScaleManager, FlowLayout), ne samo FlowLayout.

### Šta je vraćeno

- `gui/tabs/faktura_view.py` + dist_client: originalni `QGridLayout`
  toolbar (stretch 1:3:3:5:3, `_create_thick_separator()` separatori,
  `setFixedWidth(90)` na Bruto/Neto bez `register_fixed_size`).
- `gui/widgets/flow_layout.py` + dist_client: obrisani (novi fajlovi ove
  sesije, nikad nisu postojali prije).
- `gui/main_window.py`/`run.py` + dist_client: bez promjena potrebnih —
  neto diff između stanja prije `c62601b` i `347a8de` (HEAD) za ove fajlove
  je NULA (uzastopni commitovi su se međusobno poništili).
- `gui/utils/scaling.py` + dist_client: ostaju obrisani (već obrisani u
  `347a8de`, nisu postojali ni prije `c62601b`).

### Tehnika (partial-revert uz nepovezan WIP)

`faktura_view.py` ima nepovezan unstaged WIP (`_validation_issue_counts`)
preko cijelog toolbar redizajna. Korišten `git stash push -- <files>` →
`git checkout 05354ef -- <files>` (vraća na pre-scaling stanje) →
`git stash pop` (3-way merge WIP-a, bez konflikta) → INDEX eksplicitno
resetovan na čisti `05354ef` (`cp` worktree u temp, ponovni checkout, `cp`
nazad) prije commit-a, da revert NE pokupi dio WIP-a slučajno.

### Rezultat

Originalni problem (toolbar ~2247px, ne stane na 1536px laptop) je PONOVO
PRISUTAN — nije riješen, vraćeno je na stanje od početka sesije. Svi
commitovi sesije ostaju u historiji (revert, ne reset/rebase).

### Commit (dopuna 4)

| Hash | Poruka |
| --- | --- |
| `6788444` | revert(gui): vrati Faktura toolbar na originalni QGridLayout, ukloni skaliranje |
