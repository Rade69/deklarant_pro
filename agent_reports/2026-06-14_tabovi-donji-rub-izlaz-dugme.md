# Traka tabova — donji rub, pozicija i boja "Izlaz" dugmeta

## Datum
2026-06-14

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `styles/main_tabs.qss` + `dist_client/styles/main_tabs.qss`
- `gui/main_window.py` + `dist_client/gui/main_window.py`

## GitNexus impact
Provjereno PRIJE izmjene:

- `Method:gui/main_window.py:MainWindow._create_exit_button#0` (upstream)
  → **risk: LOW**, jedini poziv iz `MainWindow.__init__`, 0 pogođenih
  procesa.

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level:
"low"`, `affected_count: 0`, `affected_processes: []`. Nepovezane unstaged
izmjene (`AGENTS.md`, `CLAUDE.md`, dokumentacioni WIP) ostale netaknute /
nestaged.

## Šta je urađeno
Korisnik je poslao screenshot trake glavnih tabova (Faktura, Naimenovanja,
Zaglavlje, Šifrarnici, Admin, Agent + "Izlaz" dugme) i tražio tri ispravke:

1. **"Ne vidi se donji dio dugmadi [tabova]"** — `styles/main_tabs.qss` i
   `dist_client/styles/main_tabs.qss`: u `QTabWidget::pane` dodato
   `border-top: none; border-top-left-radius: 0;
   border-top-right-radius: 0;`.
2. **"Izlaz" dugme premjestiti bliže "Agent" tabu** — u oba
   `main_window.py`: uklonjen `tabs.setCornerWidget(btn,
   Qt.TopRightCorner)`, dodata metoda `_position_exit_button()` koja
   pozicionira dugme odmah desno od `tabBar()` (razmak 12px), pozivana iz
   novog `resizeEvent` i iz `_apply_display_profile`.
3. **Crvenija ikonica "Izlaz"** — boja power-ikonice promijenjena sa
   `#7F1D1D` na `#DC2626` (Tailwind red-600), u oba `_create_exit_button`.

## Zašto je urađeno

**Provjera hipoteze** (offscreen replika trake tabova sa stvarnim
kombinovanim QSS-om iz `load_stylesheet()`, `displayProfile="compact"`,
1536x816):

- Snimljen screenshot ORIGINALNOG stanja pokazao tanku plavu horizontalnu
  liniju koja prelazi preko DONJEG dijela ikonica/teksta SVIH neaktivnih
  tabova (i kroz "IZLAZ" dugme). Uzrok: `QTabWidget::pane` border (2px,
  `#0078d4`, `border-radius: 8px`) se po default Qt ponašanju crta sa malim
  preklapanjem PREKO donjeg ruba trake tabova. Za AKTIVNI (selektovani) tab
  ova linija je nevidljiva jer mu je `background-color` ista boja kao pane
  border (`#0078d4`); za neaktivne (svjetlije) tabove linija je vidljiva i
  presijeca ikonicu/tekst — tačno korisnikov opis "ne vidi se donji dio
  dugmadi".
- Mjerenje geometrije: `tabBar` = `QRect(0,0,1080,34)` na 1536px prozoru,
  dok je `Izlaz` dugme (corner widget) bilo na `QRect(1440,-1,96,38)` —
  ogroman razmak (Agent tab završava na x=1080, Izlaz počinje na x=1440)
  zato što `setCornerWidget(Qt.TopRightCorner)` anchoruje na desni ugao
  CIJELOG `QTabWidget`-a (Expanding, širina cijelog prozora), a NE na kraj
  `tabBar()`-a.
- `#7F1D1D` je vrlo tamna/desaturisana boja koja se gotovo gubi na tamnoj
  pozadini "Izlaz" dugmeta — korisnikov zahtjev za "crvenijom" bojom je
  potvrđen vizuelno.

## Kako je urađeno

1. **main_tabs.qss** (gui + dist_client, identične datoteke): u
   `QTabWidget::pane` dodat `border-top: none` + nulirani top-corner
   radiusi, čime pane border-top linija prestaje da se crta preko trake
   tabova. Donji border + `border-radius: 8px` na donjim uglovima ostaju
   nepromijenjeni (estetika panela ostaje).
2. **main_window.py** (gui + dist_client): `btn_exit_app` se ne dodaje više
   preko `setCornerWidget`, nego kao obično dijete `tabs`
   (`setParent(tabs)`, `raise_()`, `show()`), pa ga nova metoda
   `_position_exit_button()` pomjera na `bar_rect.right() + 12`,
   vertikalno centrirano u odnosu na `tabBar()`. Pozicioniranje se
   ponovo izvršava u `resizeEvent` (novi override) i na kraju
   `_apply_display_profile` (jer promjena `tab_icon_size` mijenja širinu
   `tabBar()`-a).
3. Boja ikonice promijenjena samo u `_create_exit_button` (`qta.icon(...,
   color=...)`).

## Šta nije dirano
- `_on_exit_clicked`, `_confirm_safe_to_exit`, `_save_window_state`, ostatak
  `__init__` (tabovi, signali) — nepromijenjeni.
- Display Profile sistem (`gui/utils/display_profile.py`,
  `styles/display_profiles.qss`) — nedirano, samo se poziva postojeća
  `_apply_display_profile` sa novim dodatnim pozivom na kraju.
- Nepovezane unstaged izmjene `AGENTS.md` / `CLAUDE.md` — van scope-a,
  ostavljene nestaged.
- `client.log.lck` (untracked) — nedirano.

## Verifikacija
- `python -m py_compile gui/main_window.py dist_client/gui/main_window.py`
  → OK.
- Offscreen diagnostika (privremeni `_tmp_diag_tabs*.py`/`.png`, obrisani
  nakon provjere) sa kombinovanim pravim QSS-om (11 fajlova iz
  `load_stylesheet()`), `displayProfile="compact"`, 1536x816:
  - PRIJE: tanka plava linija kroz donji dio svih neaktivnih tabova +
    "IZLAZ" na `x=1440` (veliki razmak iza "AGENT" na `x=1080`) + ikonica
    `#7F1D1D` (gotovo nevidljiva na tamnoj pozadini).
  - POSLIJE: linija nestala (svi tabovi čisti, bez presjeka), "IZLAZ"
    pozicioniran na `x=1091` (12px iza "AGENT", `tabBar.right()=1079`),
    ikonica `#DC2626` (jasno vidljiv crveni krug oko power simbola).
  - Screenshotovi vizuelno pregledani (Read tool, multimodalno) prije i
    poslije — potvrđena ispravnost oba fixa.

## Pronađeni problemi
- U offscreen screenshotu tab "Šifrarnici" prikazuje "Š" kao mali znak
  IZNAD "ifrarnici" (umjesto normalnog "Š" u riječi). Ovo je vjerovatno
  **font-fallback artefakt offscreen/sandbox okruženja** (font "Segoe UI"
  nije dostupan, Qt koristi "Roboto -1" fallback čije metrike za "Š" su
  loše) — NIJE povezano sa korisnikovom žalbom "ne vidi se donji dio
  dugmadi" (ta je riješena pane-border fixom). Nije reproducirano niti
  popravljano; ako se isto javi na stvarnom Windows hardveru (gdje Segoe UI
  postoji), to bi bio SEPARATAN problem za istražiti.
- "Izlaz" dugme i dalje ima visinu ~38px (umjesto `setFixedHeight(30)`) —
  vjerovatno `button_system.qss` `min-height` nadjačava `setFixedHeight`.
  Sa novim pozicioniranjem ovo dugme blago (≈4-6px) zadire u prazan prostor
  panela ispod trake tabova, ali to nije vizuelno problematično (pane više
  nema border-top koji bi to istakao). Nije mijenjano — van scope-a ovog
  zadatka, spomenuto kao mogući kozmetički follow-up.

## Commitovi
| Hash | Poruka |
|------|--------|
| `e5ca8bc` | `fix(gui): popravi traku tabova - donji rub, pozicija i boja Izlaz dugmeta` |

## Rizici / ograničenja
- `_position_exit_button()` koristi `tabBar().geometry()` koja je
  ispravna SAMO nakon prvog layout prolaza — pozicioniranje se zato
  poziva i odmah u `__init__` (može biti (0,0) prije prvog show-a, ali
  `resizeEvent` pri prvom prikazu prozora ga odmah ispravi).
- Ako se u budućnosti dodaju/uklanjaju glavni tabovi ili promijeni
  `tab_icon_size` van postojećih hook-ova (`resizeEvent`,
  `_apply_display_profile`), `_position_exit_button()` treba pozvati i
  na tom mjestu — trenutno pokriva sve poznate slučajeve promjene širine
  `tabBar()`-a.

## Potreban follow-up
- Nema otvorenih stavki vezanih za originalna 3 zahtjeva. Visina "Izlaz"
  dugmeta (38px vs `setFixedHeight(30)`) je kozmetička sitnica, follow-up
  samo ako korisnik primijeti.

## Potrebna korisnička potvrda
- Pokrenuti aplikaciju i vizuelno potvrditi na stvarnom ekranu:
  1. Donji dio ikonica/teksta svih tabova (Faktura, Naimenovanja,
     Zaglavlje, Šifrarnici, Admin, Agent) je sada potpuno vidljiv, bez
     linije koja ih presijeca.
  2. "Izlaz" dugme je odmah pored "Agent" taba (mali razmak), ne na ivici
     prozora.
  3. Ikonica unutar "Izlaz" dugmeta je vidljivo crvenija (`#DC2626`) — ako
     nijansa nije po ukusu, javiti za podešavanje.
  4. (Opciono) Provjeriti da li se "Š" u "Šifrarnici" prikazuje normalno na
     stvarnom hardveru (vidi "Pronađeni problemi" — pretpostavka je da je
     to samo offscreen artefakt).
