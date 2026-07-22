# Agent Report — 2026-07-22: Selekcija za opštu validaciju (_on_validate_all)

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + `dist_client` kopija
- `tests/unit/test_faktura_view_validacija_selekcija.py` (novo)
- `project_rooms/2026-07-22_selekcija-opsta-validacija.md` (plan, HIGH impact)
- `docs/CONTEXT.md` (§38)

## Status izvora

Dio "sitnih stvari" koje je korisnik zatražio da se riješe dok Codex nastavlja svoj dio
posla — stavka iz ranije sačinjene liste follow-up-a: "Opšta validacija (`_on_validate_all`
— brojanje grešaka/upozorenja) i dalje ne poštuje selekciju, samo istorijska tarifna
provjera to sad radi."

## GitNexus impact

`_validation_issue_counts` — **HIGH** (27 impactedCount, transitivno kroz `_update_status_bar`
pozvan sa ~15 mjesta u fajlu). Po AGENTS.md pravilu za HIGH/CRITICAL, napisan
`project_rooms/2026-07-22_selekcija-opsta-validacija.md` PRIJE izmjene. Mitigacija: novi
parametar je OPCIONI sa default vrijednošću (`None`) koja zadržava IDENTIČNO ponašanje za sve
postojeće pozivaoce (svi zovu bez argumenata) — funkcionalno nulti rizik za postojeći kod
uprkos visokoj graf-povezanosti. `_on_validate_all` — LOW (potpis nepromijenjen).
`gitnexus_detect_changes()` nakon izmjene: `risk_level: low`, `affected_count: 0`.

## Šta je urađeno

1. `_validation_issue_counts(self, row_indexes: list[int] | None = None)` — kad je
   `row_indexes` zadan, iterira SAMO te redove; `None` (default) = identično staro ponašanje
   (svi redovi).
2. `_on_validate_all`: dodat identičan selekcijski obrazac kao u `_run_historical_tariff_validation`
   (`selection.selectedRows()` kad `not auto`). Bojenje redova (`_validate_and_color_row`)
   OSTAJE na SVIM redovima tabele — jeftino, tabela uvijek vizuelno ažurna bez obzira na
   selekciju. Ali brojevi u sažetku (`error_count`/`warning_count`/`valid_count`/`total_count`)
   i cijela poruka se računaju SAMO za selektovane redove kad je selekcija aktivna — direktno
   preko `validation_cache.get(row)` po svakom indeksu, ne preko globalnih
   `get_error_count()`/`get_warning_count()`/`get_valid_count()` metoda. Poruka dobija
   eksplicitnu napomenu "📌 Prikazano samo za N selektovanih stavki." na vrhu.

## Zašto je urađeno

Prije ove izmjene, "Provjeri" na 2 selektovane stavke od ukupno 94 bi ipak u sažetku
prijavio grešku/upozorenja svih 94 — potpuno nekonzistentno sa istorijskom tarifnom
provjerom koja VEĆ scopira na selekciju (§26 fix), i zbunjujuće za korisnika koji je
namjerno selektovao konkretne stavke.

## Kako je urađeno

Identičan kod-obrazac kopiran iz `_run_historical_tariff_validation`/`_on_auto_fill` (isti
`selection.selectedRows()` → `candidate_indexes` → `row_indexes` lanac) — bez izmišljanja
nove logike. Scoped brojanje implementirano ručno (petlja preko `row_indexes` sa
`validation_cache.get(row)`) jer `ValidationCache` klasa nema ugrađenu "scoped count" metodu
(provjereno u `services/faktura/validation_cache.py`) — nije dodana nova metoda tamo, samo
iskorišten postojeći `.get(row)` API sa strane pozivaoca.

## Šta nije dirano

- `ValidationCache` klasa — nula izmjena, koristi se postojeći `.get(row)`.
- Bojenje redova — i dalje na SVIM redovima uvijek (namjerno, ne samo selektovanim).
- `_run_historical_tariff_validation` — već imala svoju selekcijsku logiku prije ovog
  zadatka, nije ponovo mijenjana.
- Svi OSTALI pozivaoci `_validation_issue_counts()` (`_update_status_bar` i tranzitivno ~15
  mjesta) — pozivaju bez argumenata, ponašanje im ostaje identično.
- `auto=True` (puna automatizacija) put — potpuno netaknut, selekcijska logika se provjerava
  samo kad `not auto`.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_validacija_selekcija.py -v
  → 3 passed (novo): scoped issue counts, on_validate_all sa selekcijom (dokazuje da
    redovi VAN selekcije sa greskom u cache-u NISU racunati), on_validate_all bez
    selekcije (staro ponasanje)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 854 passed, 58 skipped, 3 failed, 1 error (identicno pretpostojecim/nepovezanim
    failovima iz prethodnih izvjestaja)
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py → OK
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

Nema novih.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | feat(faktura): "Provjeri" skopira opstu validaciju na selekciju |

## Rizici / ograničenja

- Poruka sad ima dodatnu prvu liniju kad je selekcija aktivna ("Prikazano samo za N
  selektovanih stavki") — kozmetička promjena teksta, ne utiče na logiku.

## Potreban follow-up

- Ručni test u aplikaciji: selektovati N stavki, kliknuti "Provjeri", potvrditi da sažetak
  prikazuje brojeve SAMO za te stavke (ne za cijelu fakturu).

## Potrebna korisnička potvrda

- Da li scoped sažetak radi kako se očekuje u praksi.
