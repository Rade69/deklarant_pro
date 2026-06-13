# EUR.1 dijalog: ograničenje visine tabele + analiza zaglavlja

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/dialogs/eur1_quick_dialog.py` + `dist_client/gui/dialogs/eur1_quick_dialog.py`
  (`Eur1QuickDialog._create_groups_table`)

## GitNexus impact
Prije izmjene:
- `Eur1QuickDialog._create_groups_table` — risk **LOW**, impactedCount 2
- `Eur1QuickDialog._auto_resize` — risk **LOW**, impactedCount 2
  (oba: jedini upstream poziv je `setup_ui` → `__init__`, klaster "Dialogs",
  0 execution flow-ova pogođeno)

Nakon izmjene, `gitnexus_detect_changes(scope="staged")` na 2 finalna fajla:
`risk_level: "low"`, 21 promijenjen simbol, 0 affected, 0 affected processes.

## Šta je urađeno
Korisnik je prijavio dva problema nakon testiranja Faze 1-2 (commit `3fae234`):

- **Bug A**: "EUR.1 obrazac po fakturi" dijalog je toliko velik da su OK/Cancel
  dugmići van vidljivog dijela ekrana, kad postoji puno grupa
  faktura×zemlja (screenshot: 12 grupa, "59 stavki iz 8 zemlje").
- **Bug B**: "Drugo nema uvoza u zaglavlje" — zaglavlje (izvoznik/uvoznik/valuta)
  se ne popunjava nakon importa, uz log spam
  `tipovi_deklaracija DB greška: DB circuit breaker aktivan — server privremeno
  nedostupan`.

Za Bug A: izmijenjena je `_create_groups_table` da ograniči i minimalnu I
maksimalnu visinu tabele grupa na osnovu dostupne visine ekrana, umjesto da
visina raste neograničeno sa brojem grupa.

Za Bug B: izvršena je dijagnostička analiza (bez izmjene koda) — vidi
"Zašto je urađeno" i "Pronađeni problemi".

## Zašto je urađeno
**Bug A — uzrok**: `_create_groups_table` je radio
`table.setMinimumHeight(total_h)` gdje
`total_h = header_height(46) + len(countries) * row_height(48)`. Za 12 grupa
to je 622px. `_group_by_country` grupiše po `"INVOICE_NUM - COUNTRY"`, pa
više faktura koje dijele iste zemlje porijekla (npr. 4 fakture × 8 zemalja sa
preklapanjem) eksplodira broj redova u odnosu na broj distinktnih zemalja.
`_auto_resize` poziva `resize()` na cijelom dijalogu, ali hard
`setMinimumHeight()` na child tabeli je sprečavao dijalog da se smanji ispod
te visine — OK/Cancel red je gurnut van ekrana.

**Bug B — analiza (radna hipoteza, nepotvrđena)**: Praćen je cijeli tok
popunjavanja zaglavlja: `draft` → `ZaglavljeService.load_from_draft` (čisto
dict mapiranje, bez DB pozива) → `ZaglavljeView.set_data` (popunjava
`field_widgets`), te trigger refresh-a u `MainWindow._on_tab_changed` (kad se
prebaci na Zaglavlje tab, poziva `zaglavlje_tab.load_from_draft(active_draft)`).
Sve mapiranje (`izvoznik_naziv`→`izvoznik_r1`, `primalac_naziv`→`primalac_r1`,
`valuta` fallback iz `invoice_lines[i].valuta`) je provjereno i ISPRAVNO —
nije pronađen bug u samoj logici popunjavanja zaglavlja iz Faze 1-2
(`_apply_import_result_to_header`, commit `3fae234`).

`tipovi_deklaracija DB greška: DB circuit breaker aktivan` dolazi iz
`_load_tipovi_deklaracija_from_db()` (`gui/tabs/zaglavlje_view.py:95-106`),
koja interno hvata exception, loguje warning i vraća `[]` — to NE prekida
`set_data` petlju, utiče samo na default izbor u "deklaracija_oznaka" (A/Z/B)
combo-u.

**Radna hipoteza**: Bug B može biti DIREKTNA POSLJEDICA Bug A — ako modalni
EUR.1 dijalog blokira ekran sa nedostupnim dugmićima, korisnik ne može
zatvoriti dijalog, pa import pipeline nikad ne stigne do
`_on_all_completed` (gdje `_apply_import_result_to_header` puni zaglavlje).
Ova hipoteza NIJE potvrđena testom sa stvarnom aplikacijom.

## Kako je urađeno
U `_create_groups_table` (oba fajla, identičan tekst):

```python
table.verticalHeader().setDefaultSectionSize(48)
row_height = 48
header_height = 46
total_h = header_height + len(countries) * row_height

from PySide6.QtGui import QGuiApplication
screen = QGuiApplication.primaryScreen()
available_h = (screen.availableGeometry().height() - 80) if screen else 700
max_table_h = max(header_height + row_height * 3, available_h - 300)
table_h = min(total_h, max_table_h)
table.setMinimumHeight(table_h)
table.setMaximumHeight(table_h)
return table
```

- `available_h` = dostupna visina ekrana minus 80px (taskbar/margine).
- `max_table_h` = rezerviše 300px za chrome dijaloga (header, podnaslov,
  info label, OK/Cancel red, marginе, naslovna traka), sa donjim ograničenjem
  od najmanje 3 vidljiva reda.
- `table_h = min(total_h, max_table_h)` — ako stvarni broj grupa stane,
  tabela je tačne visine (kao prije); ako ne stane, tabela se ograniči i
  ugrađeni scrollbar `QTableWidget`-a preuzima prikaz ostatka.
- `setMaximumHeight` (novo, prije nije postojalo) je ključan — bez njega
  `setMinimumHeight` sam ne sprečava dijalog od rasta preko ekrana, ali NE
  garantuje smanjenje ispod tog minimuma.

Izmjena je identično primijenjena u `gui/` i `dist_client/` (potvrđeno
identičan kontekst linija 227-232 prije izmjene).

## Šta nije dirano
- **Bug B** — NIJE napravljena nikakva izmjena koda za zaglavlje
  (`zaglavlje_view.py`, `zaglavlje_service.py`, `zaglavlje_tab.py`,
  `main_window.py`, `faktura_view.py`). Razlog: analiza nije pronašla bug u
  postojećoj logici, a radna hipoteza (posljedica Bug A) zahtijeva re-test od
  korisnika PRIJE bilo kakve dalje izmjene — da se ne "popravlja" nešto što
  možda nije zaista pokvareno.
- **DisplayProfile WIP** (nepovezan, nekomitovan posao u toku): `AGENTS.md`,
  `gui/main_window.py`, `dist_client/gui/main_window.py`,
  `gui/tabs/faktura_view.py`, `dist_client/gui/tabs/faktura_view.py`,
  `gui/utils/display_profile.py`, `dist_client/gui/utils/display_profile.py`,
  `styles/display_profiles.qss`, `dist_client/styles/display_profiles.qss`,
  `tests/unit/test_display_profile.py`, `client.log.lck`,
  `.codex_toolbar_preview.png` — ostaju nestaged/netaknuti.
- **EUR.1/PE2/PE3 dijalog arhitektura** (per-faktura vs zajednički) — ostaje
  nepromijenjena, van scope-a (odluka iz prethodne sesije).

## Verifikacija
- `python -m py_compile gui/dialogs/eur1_quick_dialog.py dist_client/gui/dialogs/eur1_quick_dialog.py`
  — OK.
- Offscreen test skripta (privremena, obrisana nakon) sa `QT_QPA_PLATFORM=offscreen`:
  - Konstruisan `Eur1QuickDialog` sa 60 `InvoiceLine` objekata raspoređenih u
    12 grupa faktura×zemlja (2503393-2503396 × CN/IT/DE/DK/FR/RO/SK/IN/TW/CH),
    isti broj grupa kao u korisnikovom screenshotu.
  - Prije fix-a: `total_h = 622px` (12 grupa × 48 + 46).
  - Poslije fix-a, na offscreen ekranu 800×800 (`available_h = 720`,
    `max_table_h = max(190, 420) = 420`): `groups_table.height() == 420`,
    `minimumHeight == maximumHeight == 420`.
  - Dialog ukupna veličina: 820×627. `ok_button` geometrija:
    `y=571, height=42` → bottom=613 ≤ 627 (unutar dijaloga) i ≤ 720
    (unutar dostupnog ekrana) — OK/Cancel red je vidljiv.
  - Na realnim ekranima (laptop ~1536×~870, monitor 1920×1032)
    `available_h` je veći → `max_table_h` veći → manje/nikakvo skraćivanje
    tabele potrebno za isti broj grupa.
  - Nije bilo Python exception-a pri konstrukciji.

## Pronađeni problemi
Nema novih problema u kodu pronađenih za Bug B — vidi "Zašto je urađeno" za
detalje analize i radnu hipotezu koja povezuje Bug B sa Bug A.

## Commitovi
| Hash | Poruka |
|------|--------|
| `776b06e` | fix(gui): ogranici visinu EUR.1 tabele da OK/Cancel ostanu vidljivi |

## Rizici / ograničenja
- Fix je testiran OFFSCREEN (virtuelni ekran 800×800) — stvarni izgled na
  korisnikovom laptopu/monitoru NIJE vizuelno potvrđen.
- `max_table_h` formula (`available_h - 300`) koristi fiksnu procjenu od
  300px za "chrome" dijaloga (header/podnaslov/info/dugmići/margine). Ako
  je stvarni chrome veći na nekom ekranu/temi, tabela bi mogla i dalje biti
  malo previsoka — ali `setMaximumHeight` garantuje da tabela SAMA neće biti
  uzrok preljeva, jer dijalog (`_auto_resize`) i scrollbar tabele preuzimaju
  ostatak.
- Bug B fix NIJE napravljen — i dalje moguće da postoji nakon re-testa.

## Potreban follow-up
- **Bug B**: korisnik treba ponovo testirati uvoz fakture (koji aktivira
  EUR.1 dijalog sa puno grupa) NAKON ovog fix-a. Ako se "Drugo nema uvoza u
  zaglavlje" i dalje javlja i kada se EUR.1 dijalog normalno zatvori, treba
  novi zadatak za dublju istragu DB circuit breaker mehanizma i njegovog
  uticaja na ostatak importa.
- DisplayProfile WIP ostaje odvojen, nezavršen posao iz prethodnih sesija.

## Potrebna korisnička potvrda
- Otvoriti uvoz fakture koji generiše puno EUR.1 grupa (faktura×zemlja, kao
  u screenshotu sa 12 grupa) i potvrditi da su OK/Cancel dugmići vidljivi i
  klikabilni, te da se preostale grupe mogu vidjeti scroll-ovanjem tabele.
- Nakon zatvaranja EUR.1 dijaloga, provjeriti da li se zaglavlje
  (izvoznik/uvoznik/valuta) ipak popuni — ako DA, Bug B je bio posljedica
  Bug A i ovaj fix ga rješava; ako NE, potreban je dodatni zadatak za Bug B.
