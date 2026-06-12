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

## Napomena / mogući follow-up

- 1536px ekran i dalje ima ~260px "viška" (1797 vs 1536) jer pojedini
  elementi (npr. inline QSS `font-size: 14px/17px` na bruto/neto labelama i
  section header dugmadima) ne reaguju na `QApplication.setFont()`. Ako
  korisnik i dalje primijeti squishing na malom ekranu, sljedeći korak bi bio
  da `ScaleManager` rewrituje i te inline QSS font-size vrijednosti
  proporcionalno scale faktoru.
