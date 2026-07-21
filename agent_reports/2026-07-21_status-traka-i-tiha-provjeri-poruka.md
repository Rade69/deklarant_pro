# Agent Report — 2026-07-21: Status traka (Komada/Porijeklo) i tiha "Provjeri" poruka

## Datum
2026-07-21

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_view_status_bar.py` (novo)
- `tests/unit/test_faktura_view_provjeri_selekcija.py` (dopuna, 2 nova testa)
- `docs/CONTEXT.md` (dopuna 4, §27)

## Status izvora

Direktan nastavak `agent_reports/2026-07-21_provjeri-postuje-selekciju-redova.md` — korisnik
je testirao rebuildovani `.exe` (17:56) i prijavio 3 nalaza na jednom screenshotu statusne
trake: (1) klik na "Provjeri" nakon selekcije nije otvorio modal iako je mislio da bi trebao,
(2) "Komada: 8,045.0" — decimalan prikaz količine, (3) "Porijeklo: 9 zemalja" umjesto ranijeg
breakdown-a po zemlji ("DE|9:IT|8...").

## GitNexus impact

- `_build_analysis_summary_from_draft` — LOW (1 direktan pozivalac
  `_refresh_analysis_summary_from_draft`, 0 affected_processes, 21 impactedCount ukupno kroz
  transitivni lanac `_update_status_bar` → mnoge UI akcije, ali sve preko istog stabilnog
  povratnog `tuple[str, str]` potpisa — mijenjan samo SADRŽAJ teksta, ne potpis).
- `_run_historical_tariff_validation` — LOW (potvrđeno više puta isti dan, potpis
  nepromijenjen).
- `_update_status_bar` — nije zaseban target za impact (formatting-only linija unutar
  postojeće metode).
- `gitnexus_detect_changes()` nakon izmjene: `risk_level: low`, `affected_count: 0`.

## Šta je urađeno

**1) "Provjeri" bez prijedloga za selektovane stavke — tišina zamijenjena porukom.**
Prošli fix (selekcijsko scoping) je otkrio latentan problem: `if not matches: return` grana
nije NIKAD davala korisniku ikakvu potvrdu. Prije scoping-a to se rijetko primjećivalo (94
stavki skoro uvijek nešto vrati); sad kad korisnik selektuje 1-2 stavke i ništa se ne desi,
to izgleda kao da je dugme "otkazalo". Dodato: `QMessageBox.information` SAMO kad je
`row_indexes is not None` (aktivna selekcija) i nema `auto_applied` stavki — bez selekcije
tišina ostaje namjerna (ne prekidati korisnika porukom na svaki klik kad se provjerava cijela
faktura od desetina stavki).

**2) "Komada" prikazivalo decimalan broj.** `lbl_total_quantity.setText(f"📦 Komada:
{total_quantity:,}")` — `total_quantity` je zbir `item.kolicina` (float polje), pa je
`8045.0` prikazivano kao `"8,045.0"`. U carinskom postupku količina komada MORA biti cio
broj. Fix: `int(round(total_quantity))` prije formatiranja.

**3) "Porijeklo" izgubilo breakdown po zemlji.** Otkriveno u git istoriji: komit `735400a`
("style(faktura): sažmi statusnu traku", Co-Authored-By: OpenAI Codex, 2026-07-21 16:44) je
namjerno zamijenio `"🌍 DE:9 | IT:8"` format sa `"🌍 Porijeklo: 9 zemalja"` — gubeći
informaciju koliko naimenovanja pripada kojoj zemlji. Korisnik je eksplicitno tražio da se
breakdown vrati. Vraćen originalni `zemlja_str` format (isti kod koji je postojao prije tog
komita).

## Zašto je urađeno

1. Bez eksplicitne poruke, korisnik gubi povjerenje da funkcija uopšte radi kad selektuje
   konkretne stavke i ne dobije nikakav odgovor — potpuno opravdano pitanje "da li je trebalo
   da se otvori dijalog".
2. Carinski propis: količina robe (komada) je uvijek cio broj — decimalan prikaz je vizuelno
   pogrešan i zbunjuje pri provjeri deklaracije.
3. Breakdown po zemlji je aktivno korištena informacija (korisnik je eksplicitno primijetio
   njen nestanak i zatražio povratak) — kompresija u "9 zemalja" gubi upravo podatak koji je
   koristan za brzu provjeru raspodjele porijekla robe.

## Kako je urađeno

- `_run_historical_tariff_validation`: dodat `QMessageBox.information(...)` poziv unutar
  postojeće `if not matches:` grane, uslovljen sa `row_indexes is not None and not
  auto_applied` — minimalna izmjena, ne dira ostatak kontrolnog toka.
- `_update_status_bar`: `int(round(total_quantity))` umjesto `total_quantity` direktno u
  f-stringu — jednolinijska izmjena, ne dira izračun zbira niti druge label-e.
- `_build_analysis_summary_from_draft`: vraćen `zemlja_str`/`text = f"🌍 {zemlja_str}"` blok
  (identičan kodu prije komita 735400a), uklonjen `country_label`/kompresovani `text`.
- `dist_client` mirroring: `_update_status_bar` i `_run_historical_tariff_validation` regioni
  su bili identični root-u prije izmjene, izmjene primijenjene identično. Za breakdown po
  zemlji, `dist_client` je VEĆ imao stari (ispravan) format — provjereno da je identičan
  root-ovom nakon fix-a, izmjena u dist_client NIJE bila potrebna za tu tačku.

## Šta nije dirano

- Opšta validacija (`_on_validate_all` error/warning brojanje) — i dalje radi na svim
  redovima, van scope-a ovog zadatka.
- `HistoricalTariffSearchService`, `user_feedback` mehanizam.
- Ostatak komita `735400a` (druge stilske izmjene statusne trake) — samo ova jedna linija je
  vraćena, ne cijeli komit.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_status_bar.py tests/unit/test_faktura_view_provjeri_selekcija.py -v
  → 9 passed (3 nova + 2 nova + 4 postojeća)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 839 passed, 58 skipped, 3 failed, 1 error (identično pretpostojećim/nepovezanim
    failovima iz prethodnih izvještaja istog dana)
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py → OK
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

`build_windows.bat` ima sitan, nepovezan bug u repić dijelu skripte (poruka o kopiranju XML
arhive) — cmd.exe "was unexpected at this time" zbog zagrada unutar echo teksta u
if/else bloku. Ne utiče na sam `.exe` (build je već završen prije tog koraka), samo na
kozmetičku poruku na kraju skripte. Nije popravljano u ovoj sesiji (van scope-a, korisnik
nije tražio) — flagovano korisniku, follow-up ako se traži.

## Konflikti / kontradiktorni izvori

`_build_analysis_summary_from_draft` breakdown format: komit `735400a` (Codex,
"sažmi statusnu traku") je EKSPLICITNO uklonio breakdown format kao stilsku odluku. Korisnik
je sad eksplicitno tražio da se vrati. Tretiran kao važeći: korisnikov najnoviji zahtjev
(direktan feedback nadjačava raniju stilsku odluku drugog agenta). Nije potrebna dodatna
korisnička potvrda — zahtjev je bio nedvosmislen ("prije je tu stajalo... trebalo bi da se
vrati" implicitno kroz opis problema).

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | fix(faktura): status traka i tiha "Provjeri" poruka |

## Rizici / ograničenja

- Poruka za "nema prijedloga" se prikazuje na SVAKI klik "Provjeri" kad je selekcija aktivna
  i nema prijedloga — ako korisnik ponavlja klik na iste stavke, može postati ponavljajuća
  (isti rizik kao već dokumentovano za `_notify_auto_applied_tariffs`).
- `build_windows.bat` repić bug nije popravljen (kozmetički, van scope-a).

## Potreban follow-up

- Ručni test na rebuildovanom `.exe`-u: potvrditi da su sva tri nalaza riješena.
- Razmotriti popravku `build_windows.bat` repić bug-a ako postane smetajuće.

## Potrebna korisnička potvrda

- Da li su sva tri nalaza (tiha "Provjeri" poruka, cio broj komada, breakdown po zemlji)
  riješena kako je očekivano na rebuildovanom `.exe`-u.
