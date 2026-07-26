# Opis tarife u dijalogu "Automatski ažurirane tarife"

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/faktura_view.py` — `_build_tariff_table_widget` (novo),
  `_show_tariff_preview_dialog` (refaktorisan), `_show_tariff_table_info_dialog`
  (novo), `_notify_auto_applied_tariffs` (izmijenjen)
- `dist_client/gui/tabs/faktura_view.py` — ista izmjena, mirror
- `tests/unit/test_faktura_view_auto_applied_notice.py`
- `docs/CONTEXT.md` — §67

## Status izvora
Korisnik je uporedio dva screenshot-a iz žive aplikacije (nakon uvoza
fakture): dijalog "Potvrda auto-popunjavanja tarifnih brojeva" (tabela sa
opisom tarife) naspram "Automatski ažurirane tarife (ranija potvrda)"
(goli tekst bez opisa). Nije bilo ranijeg agent_report/memorije o ovoj
konkretnoj primjedbi — nov zahtjev, bez konflikta sa postojećim izvorima.

## GitNexus impact
- `_notify_auto_applied_tariffs` upstream: LOW (7 impacted, 1 direktan
  pozivalac — `_on_historical_validation_finished`, 0 affected_processes).
- `_show_tariff_preview_dialog` upstream: LOW (1 impacted, direktan
  pozivalac `_on_auto_fill`, 0 affected_processes).
- `detect_changes(scope=all)` nakon izmjene: LOW risk, 0 affected_processes,
  samo "touched" na `FakturaView` metodama u istom fajlu + testu.

Prijavljeno korisniku prije izmjene (LOW, bezbjedno za izmjenu).

## Šta je urađeno
1. Izdvojena `_build_tariff_table_widget(rows)` — zajednička
   Rb/Naziv/Tarifa/Izvor/Opis tabela (identična stilizacija kao ranije u
   `_show_tariff_preview_dialog`), prima listu dict-ova.
2. `_show_tariff_preview_dialog` refaktorisan da gradi `rows` i poziva
   helper — ponašanje nepromijenjeno (isti Potvrdi/Odustani tok), samo
   duplicirana stilizacija (~50 linija) uklonjena.
3. Nova `_show_tariff_table_info_dialog(title, intro_html, rows)` — OK-only
   varijanta (bez Potvrdi/Odustani, jer je tarifa već primijenjena).
4. `_notify_auto_applied_tariffs` sad gradi `rows` sa
   `opis=self._get_tariff_description(tarif)` i `izvor="Ranija ručna
   potvrda (100%)"`, poziva novi tabelarni dijalog umjesto
   `_show_scrollable_info_dialog`.
5. Ista izmjena primijenjena na `dist_client/gui/tabs/faktura_view.py`
   (bio bajt-identičan root fajlu prije izmjene, potvrđeno `git diff
   --no-index --ignore-cr-at-eol`).

## Zašto je urađeno
Korisnička primjedba: deklarant mora vidjeti OPIS nove tarife odmah, ne
tražiti ga naknadno u tarifniku/PDF-u/šifarniku — to remeti radni tok.
Prvi dijalog (prijedlog PRIJE upisa) je već imao ovu funkcionalnost; drugi
dijalog (obavijest o VEĆ primijenjenim tarifama zbog ranije ručne potvrde)
je bio manje sadržajan iz istorijskih razloga (dodat ranije, 2026-07-21,
kao čisto tekstualna transparentnost — vidi
`project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md`), bez opisa.

## Kako je urađeno
Zajednička tabela izdvojena da izbjegne duplikaciju QSS stilizacije i da
oba dijaloga izgledaju vizuelno identično (isti "sistem", ne dvije
različite implementacije istog koncepta). `_get_tariff_description` je
već postojeća metoda (koristi `TariffService.load_hierarchical_label` sa
cache-om) — samo pozvana sa NOVIM (upisanim) tarifnim kodom iz
`auto_applied` tuple-a.

## Šta nije dirano
- `_notify_auto_rejected_tariffs` (dijalog za ODBIJENE prijedloge) —
  namjerno ostavljen kako jeste, van scope-a primjedbe (nema promjene
  tarife tu, pa opis nove tarife nije direktno koristan; follow-up ako
  korisnik zatraži isto).
- `_show_scrollable_info_dialog` — i dalje postoji, koristi je
  `_notify_auto_rejected_tariffs`.
- `HistoricalTariffSearchService.validate_lines()` / `last_auto_applied`
  tuple shape — nepromijenjeno (i dalje `(idx, tarif)`, bez starog koda).

## Verifikacija
- `python -m py_compile` na oba fajla (root + dist_client) — čisto.
- `git diff --no-index --ignore-cr-at-eol` root vs dist_client nakon
  izmjene — 0 razlika (fajlovi ponovo bajt-identični, osim CRLF/LF).
- `pytest tests/unit/test_faktura_view_auto_applied_notice.py -q` — 2
  passed (ažurirani testovi).
- Pun test suite `pytest tests/ -q` — 1178 passed, 57 skipped, 5 xfailed,
  1 nepovezan pre-postojeći fail (`test_xml_parser_fix.py`) + 1 nepovezan
  error (`test_model_benchmark.py`, fixture `model_name` ne postoji).
- `gitnexus_detect_changes(scope=all)` — LOW risk, 0 affected_processes.

## Pronađeni problemi
Nema — čisto planirano UX poboljšanje po eksplicitnom korisničkom zahtjevu.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `feat(faktura): dodaj opis tarife u dijalog auto-primijenjenih tarifa` |

## Rizici / ograničenja
Vizuelna promjena — nije UI-testirana u živoj aplikaciji (offscreen Qt
test okruženje pokriva strukturu poziva, ne stvaran render). Preporuka:
korisnik potvrdi izgled na sljedećem uvozu fakture koji pogodi ovaj
dijalog (potreban je bar jedan artikal sa ranijom ručnom "Provjeri"
potvrdom da bi se `_notify_auto_applied_tariffs` uopšte pozvao).

## Potreban follow-up
- Ako korisnik želi, primijeniti isti obrazac (opis tarife) i na
  `_notify_auto_rejected_tariffs`.
- Vizuelna potvrda u živoj aplikaciji (v. "Rizici" iznad).

## Potrebna korisnička potvrda
Da — vizuelni izgled novog dijaloga na stvarnom uvozu (Qt test ne
provjerava render, samo strukturu podataka proslijeđenu u tabelu).
