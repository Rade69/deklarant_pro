# Dugme za gašenje aplikacije pored Agent taba

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/main_window.py` + `dist_client/gui/main_window.py` — novo dugme za izlaz (corner widget)
- `gui/tabs/zaglavlje_view.py` + `dist_client/gui/tabs/zaglavlje_view.py` — uklanjanje starog "Izlaz" dugmeta
- `gui/tabs/zaglavlje_controller.py` + `dist_client/gui/tabs/zaglavlje_controller.py` — uklanjanje `_on_close` handlera

## GitNexus impact
Prije izmjene provjereno (ambiguous bare-name zahtijevalo `target_uid`):
- `ZaglavljeController._on_close` — `impactedCount: 0`, LOW rizik (niko ne poziva osim signala koji se uklanja).
- `close_requested` signal — `impactedCount: 0`, LOW rizik.
- `_create_toolbar` — `impactedCount: 2` (`_setup_ui` → `__init__`), LOW rizik, očekivan lanac.

## Šta je urađeno
- Novo dugme `btn_exit_app` (ikonica `fa5s.power-off`, boja `#7F1D1D`) postavljeno
  kao `tabs.setCornerWidget(btn, Qt.TopRightCorner)` — vizuelno desno od Agent taba.
- Klik na dugme: provjeri da Agent ne procesira u pozadini → snimi Zaglavlje draft → zatvori prozor.
- Staro dugme "Izlaz" (`fa5s.sign-out-alt`, `close_requested` signal,
  `ZaglavljeController._on_close`) potpuno uklonjeno iz Zaglavlje taba (view + controller).

## Zašto je urađeno
Korisnikov zahtjev: jedinstveno, lako dostupno dugme za izlaz iz aplikacije
(prepoznatljiva "power" ikonica), umjesto skrivenog dugmeta unutar Zaglavlje
taba. Uz dodatni zahtjev: prije gašenja provjeriti da je to bezbjedno —
implementirano kao provjera da Agent (`ProcessingWorker`, QThread) ne radi u
pozadini, jer bi prekid usred procesiranja mogao ostaviti nekompletne DB
zapise.

## Kako je urađeno
- `MainWindow.__init__`: dodat `self.btn_exit_app = self._create_exit_button()`
  i `tabs.setCornerWidget(self.btn_exit_app, Qt.TopRightCorner)` —
  prvi `setCornerWidget` u repou.
- Nove metode `_create_exit_button`, `_on_exit_clicked`, `_confirm_safe_to_exit`.
- `_confirm_safe_to_exit` provjerava `self.agent_tab.controller._worker.isRunning()`
  (isti pattern kao postojeća provjera u `agent_controller.py` linije 265/712);
  ako radi, `QMessageBox.question` (Yes/No, default No) — Cancel = ne zatvaraj.
- `_on_exit_clicked` poziva `self.zaglavlje_tab.save_to_draft()` (bezbjedno i ako
  Zaglavlje LazyTab nije inicijalizovan — `__getattr__` vraća `_noop`), zatim
  `self.close()`. DB connection cleanup već centralizovano u `run.py main()`
  (`finally` blok nakon `app.exec()`), nije duplirano.
- `zaglavlje_view.py`: uklonjen `close_requested` signal, `self.btn_izlaz`,
  `"fa5s.sign-out-alt"` iz `icon_colors`, kreiranje i `addWidget` dugmeta u
  `_create_toolbar`, te connect u `_connect_signals`.
- `zaglavlje_controller.py`: uklonjen connect `close_requested → _on_close`
  (docstring + `_connect_signals`) i cijela metoda `_on_close`.
- Sve izmjene identično ponovljene u `dist_client/` mirroru.

## Šta nije dirano
- `ui/zaglavlje_tab_ui.py` + `dist_client/ui/zaglavlje_tab_ui.py` — legacy
  generisani Qt Designer fajl sa svojim nezavisnim `btn_izlaz` definicijama
  (linije 56-58, 617); potvrđeno `grep`-om da `Ui_ZaglavljeTab` nigdje nije
  importovan — dead code, van scope-a.
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py` —
  postojeći nekomitovani WIP (compact weight label stilizacija,
  `_weight_rows`/`_weights_layout`), nepovezan sa ovim zadatkom — ostavljen
  netaknut i unstaged.
- `database/db.py:close_all_connections()` — već se zove centralno u
  `run.py`, nije duplirano u novom dugmetu.

## Verifikacija
- `python -m py_compile` na svih 6 izmijenjenih fajlova — OK.
- Offscreen test (`QT_QPA_PLATFORM=offscreen`, privremena skripta, obrisana
  nakon): konstruisan `MainWindow()` bez exceptiona.
  - `tabs.cornerWidget(Qt.TopRightCorner) is win.btn_exit_app` → `True`
  - tip `QPushButton`, tooltip `"Zatvori aplikaciju"`, objectName `"btnExitApp"`,
    ikonica učitana (nije null)
  - Zaglavlje view: `hasattr(view, "btn_izlaz")` → `False`,
    `hasattr(view, "close_requested")` → `False`
  - `_confirm_safe_to_exit()` (worker `None`) → `True`
  - `win.close()` bez exceptiona

## Pronađeni problemi
- `gitnexus_detect_changes(scope="staged")` nakon stage-a samo 6 ciljanih
  fajlova prijavio "high" risk i markirao `MainWindow.continue_with_pending_declaration`,
  `_replace_draft_contents`, `_reload_all_tabs_from_draft` kao "touched" (gui/
  i dist_client/). Provjera `git diff` potvrdila: te metode NISU dotaknute —
  diff sadrži samo import liniju, `__init__` insert i 3 nove metode iza
  `_tab_icon`. Lažno pozitivno — uzrok je line-shift (47 novih linija ranije
  u fajlu pomjera line-range granice nižih simbola), ne stvarna izmjena.
  Zabilježeno u memoriji za buduće sesije.

## Commitovi
| Hash | Poruka |
|------|--------|
| `8107f24` | `feat(gui): dugme za bezbjedno gasenje aplikacije pored Agent taba` |

## Rizici / ograničenja
- Provjera "bezbjednog gašenja" pokriva samo Agent `ProcessingWorker`. Drugi
  eventualni background poslovi (npr. import workeri u drugim tabovima) nisu
  provjereni — trenutno ih nema kao dugotrajnih QThread-ova izvan Agenta.
- `setCornerWidget(Qt.TopRightCorner)` zauzima taj slot — buduće globalno
  dugme (npr. help/settings) treba `Qt.TopLeftCorner` ili kombinovani widget.

## Potreban follow-up
- Nema poznatih otvorenih stavki za ovaj zadatak.

## Potrebna korisnička potvrda
- Vizuelni izgled dugmeta (ikonica, boja, pozicija pored Agent taba) na
  stvarnom ekranu.
- Tooltip "Zatvori aplikaciju" se prikazuje na hover.
- Klik na dugme kad Agent NE radi → snimi draft i zatvori app normalno.
- Klik na dugme DOK Agent procesira fajlove → prikazuje se upozorenje
  "Agent još radi" sa Yes/No; No otkazuje zatvaranje, Yes zatvara.
- Zaglavlje tab vizuelno više nema "Izlaz" dugme u toolbaru.
