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
