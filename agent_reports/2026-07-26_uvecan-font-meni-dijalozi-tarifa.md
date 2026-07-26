# Uvećan font: kontekstni meni, dijalog izmjene tarife, tabela auto-primijenjenih tarifa

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/faktura_view.py` — `_on_table_context_menu`, `_on_bulk_change_tariff`,
  `_build_tariff_table_widget`, `_show_tariff_preview_dialog`, `_show_tariff_table_info_dialog`
- `dist_client/gui/tabs/faktura_view.py` — ista izmjena, mirror

## Status izvora
Korisnička primjedba uz dva screenshot-a iz žive aplikacije: dijalog
"Promijeni tarifni broj" (desni klik → izmjena tarife za više odabranih
stavki) i tabela u dijalogu "Automatski ažurirane tarife" (§67) imaju
premali/nečitljiv font; isto i sam kontekstni meni (desni klik) za izbor
akcije. Nema ranijeg izvještaja o ovoj primjedbi.

## GitNexus impact
- `_on_table_context_menu` upstream: LOW (0 impacted — izolovan Qt signal
  handler, jedini poziv je preko `customContextMenuRequested` signala).
- `_build_tariff_table_widget` upstream: LOW (5 impacted, direktno samo
  `_show_tariff_preview_dialog` i `_show_tariff_table_info_dialog`).
- `detect_changes(scope=unstaged)` nakon izmjene: LOW risk, 0
  affected_processes. Jedan lažno pripisan simbol
  (`_show_scrollable_info_dialog`) provjeren `git diff` — samo pomjeren
  linijski broj, tijelo netaknuto.

## Šta je urađeno
1. **`_on_table_context_menu`** — `QMenu` dobio eksplicitan stylesheet
   (`font-size: 15px`, veći padding po stavci menija).
2. **`_on_bulk_change_tariff`** — `QInputDialog.getText()` (statička
   convenience metoda, ne dozvoljava stylesheet injection) zamijenjena
   ručnom `QInputDialog` instancom (`setLabelText`/`setTextValue`/`exec`)
   sa `font-size: 15px` na labeli/input polju i `14px` na dugmadima.
   Ponašanje identično (isti povratni tekst/ok flag), samo čitljivije.
3. **`_build_tariff_table_widget`** — font stavki tabele 13px→16px, header
   eksplicitno postavljen na 15px (Qt QSS ne kaskadira `font-size` sa
   `QTableWidget` na `QHeaderView::section` automatski), padding povećan
   za bolju čitljivost uz veći font.
4. **`_show_tariff_preview_dialog`** i **`_show_tariff_table_info_dialog`**
   — intro `QLabel` tekst dobio `font-size: 15px`, OK/Potvrdi/Odustani
   dugmad `font-size: 14px` (prije nedeklarisano na svim ovim mjestima,
   nasljeđivalo globalni app font od 9pt).

## Zašto je urađeno
Ovi dijalozi/meniji nisu imali nikakav eksplicitan stylesheet, pa su
nasljeđivali globalni app font (Segoe UI 9pt na Windows-u, postavljen u
`run.py`) — za guste tabele i rijetko korišćene akcione dijaloge to je
ispalo nečitljivo malo, potvrđeno korisničkim screenshot-ovima.

## Kako je urađeno
Svuda gdje je već postojao lokalni `setStyleSheet()` poziv (npr. tabela iz
§67), samo je font-size vrijednost povećana. Gdje stylesheet nije postojao
(QMenu, QInputDialog static call), dodat je novi — za `QInputDialog` je to
zahtijevalo zamjenu statičke `.getText()` metode ručnom instancom, jer
statička metoda ne vraća referencu na dijalog prije izvršavanja.

## Šta nije dirano
- Globalni app font (`run.py`, 9pt Segoe UI) — nije mijenjan, samo lokalni
  override na ova tri mjesta koja je korisnik konkretno naveo.
- Ostali kontekstni meniji i dijalozi u aplikaciji van scope-a ove
  primjedbe — nisu dirani (moguć follow-up ako se pokaže da imaju isti
  problem).

## Verifikacija
- `python -m py_compile` na oba fajla (root + dist_client) — čisto.
- Offscreen sanity check (`QT_QPA_PLATFORM=offscreen`) — `QInputDialog`
  sa novim stylesheet-om konstruiše se bez greške.
- `pytest tests/unit/test_faktura_view_auto_applied_notice.py -q` — 2
  passed (i dalje, ne testira render).
- Pun test suite: 1262 passed, 85 skipped, 5 xfailed, ista 2
  pre-postojeća nepovezana problema.
- `gitnexus_detect_changes(scope=unstaged)` — LOW risk, 0
  affected_processes.
- `diff --strip-trailing-cr` (uz BOM-strip) potvrdio da su root i
  dist_client kopije semantski identične nakon izmjene.

## Pronađeni problemi
Nema — čisto vizuelno poboljšanje čitljivosti po eksplicitnom korisničkom
zahtjevu.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `fix(faktura): uvecaj font u kontekstnom meniju i dijalozima tarife` |

## Rizici / ograničenja
Vizuelna promjena nije potvrđena pixel-tačno (Qt offscreen test provjerava
samo da se stylesheet postavi, ne stvaran render) — potrebna korisnička
vizuelna potvrda uživo.

## Potreban follow-up
Ako korisnik primijeti da su i drugi meniji/dijalozi u aplikaciji
premalog fonta, proširiti isti tretman na njih (nije urađeno sada jer
nisu eksplicitno navedeni).

## Potrebna korisnička potvrda
Da — vizuelni izgled sva tri mjesta uživo u aplikaciji (kontekstni meni,
dijalog "Promijeni tarifni broj", tabela "Automatski ažurirane tarife").
