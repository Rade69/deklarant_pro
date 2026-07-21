# Agent Report — 2026-07-21: "Provjeri" poštuje selekciju redova

## Datum
2026-07-21

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_view_provjeri_selekcija.py` (novo)
- `docs/CONTEXT.md` (dopuna 3, §27)

## Status izvora

Direktan nastavak `agent_reports/2026-07-21_transparentnost-auto-primijenjenih-tarifa.md`.
Korisnik je nakon testiranja prijavio: nakon selektovanja stavki u tabeli i klika na
"Provjeri", tarifni brojevi "koji su došli iz fakture" ostaju nepromijenjeni čak i nakon
prihvatanja prijedloga. Prvobitne hipoteze (sortiranje tabele, prepisivanje ćelije,
signal blocking gap) provjerene i isključene u prethodnoj sesiji. Korisnikovi odgovori na
razjašnjavajuća pitanja nisu direktno odgovorili na pitanje "koje dugme/kad tačno", ali su
oba puta ponovila isti kontekst: selektuje N stavki PA klikne "Provjeri" (dugme pored
Bruto/Neto u toolbaru) — što je jak signal da je stvarni problem nedostajuća selekcijska
logika, ne opisani "revert" per se.

## GitNexus impact

`FakturaView._run_historical_tariff_validation` — LOW (potvrđeno u prethodnom izvještaju
istog dana: 1 direktan pozivalac `_on_validate_all`, 0 affected_processes; potpis metode
nepromijenjen). Live provjera u ovoj sesiji nije bila moguća (`gitnexus_impact` je vratio
grešku — LadybugDB zaključan od drugog procesa koji indeksira), pa se oslonjeno na već
utvrđen LOW rizik iz istog dana za istu funkciju. `gitnexus_detect_changes()` nakon izmjene:
`risk_level: low`, `affected_count: 0`.

## Šta je urađeno

`_run_historical_tariff_validation`: kad `auto=False` i tabela ima aktivnu selekciju
redova, `target_lines` se gradi SAMO od selektovanih redova (isti obrazac kao
`_on_auto_fill`/`selected_row_indexes`) i prosljeđuje se servisu umjesto cijele
`draft.invoice_lines` liste. Nakon poziva `validate_lines()`, `match.line_index` (na svakom
vraćenom prijedlogu) i `auto_applied` tuple-ovi se remapiraju nazad na stvarni red u tabeli
(`row_indexes[local_idx]`) — bez ovoga bi `_on_accepted`/auto-apply put upisao promjenu na
POGREŠAN red (indeks 0..N-1 unutar filtrirane selekcije, ne stvarni red tabele).

## Zašto je urađeno

Bez selekcijskog filtera, "Provjeri" na fakturi sa npr. 94 stavke uvijek prikazuje
prijedloge za SVE redove sa istorijskim tragom — korisnik koji je namjerno selektovao 1-2
konkretne stavke mora skenirati dugačku listu i lako može prihvatiti prijedlog za pogrešan
red, dok njegova ciljana stavka ostaje nepromijenjena ("tarifni broj iz fakture je i dalje
tu"). Ovo u potpunosti objašnjava prijavljeni simptom bez potrebe za daljom nagađanjem.

## Kako je urađeno

Minimalna izmjena u `_run_historical_tariff_validation` (bez promjene potpisa):
- `target_lines`/`row_indexes` iz `self.table.selectionModel()` — identičan kod kao u
  `_on_auto_fill` (linija ~4364 u istom fajlu).
- Remapiranje `match.line_index` i `auto_applied` indeksa nazad na `row_indexes[local_idx]`
  ODMAH nakon `validate_lines()` poziva, prije nego što ijedan drugi dio funkcije (upis u
  tabelu, `_notify_auto_applied_tariffs`, `TariffValidationDialog`) vidi te indekse — tako
  ostatak funkcije (`_on_accepted`, auto-apply blok) radi identično bez obzira da li je
  selekcija bila aktivna.
- `HistoricalTariffSearchService.validate_lines` NIJE mijenjan — i dalje vraća indekse
  relativne na proslijeđenu listu; remapiranje se radi isključivo na strani pozivaoca.

## Šta nije dirano

- `HistoricalTariffSearchService`/`_feedback_action`/`user_feedback` tabela.
- `_on_validate_all` — opšta validacija (boje/greške/upozorenja) i dalje radi na SVIM
  redovima bez obzira na selekciju; korisnikov zahtjev se odnosio konkretno na istorijsku
  tarifnu provjeru/prijedloge, ne na opštu validaciju polja.
- `TariffValidationDialog`, `_on_accepted`, `_notify_auto_applied_tariffs` — logika
  nepromijenjena, samo primaju već ispravno remapirane indekse.
- `gui/delegates/validation_delegate.py` — provjereno: nema nesačuvanih izmjena (ranije
  pomenut paralelni rad drugog agenta je već commitovan/čist), nije diran.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_provjeri_selekcija.py -v → 4 passed (novo)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 834 passed, 58 skipped, 3 failed, 1 error (identično pretpostojećim/nepovezanim
  failovima iz prethodnog izvještaja istog dana — dist/ torch sken, cp1252 test fajl,
  hardkodovana Linux putanja, model_benchmark)
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py → OK
git diff --stat oba fajla → identično 42 insertions/1 deletion (potvrđeno da nema
  slučajnog prepisivanja postojećeg sadržaja u dist_client kopiji)
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

Nema novih, van onoga što je već dokumentovano.

## Konflikti / kontradiktorni izvori

`project_rooms/2026-07-21_faktura-segment-5-validacioni-prikaz.md` (untracked, od ranije)
pominje paralelni rad na `gui/delegates/validation_delegate.py` — provjereno da taj fajl
trenutno nema nesačuvanih izmjena (već commitovan), pa nije bilo konflikta niti rizika od
prepisivanja u ovoj sesiji.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | fix(faktura): "Provjeri" poštuje selekciju redova u tabeli |

## Rizici / ograničenja

- Opšta validacija (`_on_validate_all`'s error/warning brojanje i summary dijalog) i dalje
  NE poštuje selekciju — samo istorijska tarifna provjera je sada selekcijski svjesna. Ako
  korisnik očekuje da i taj sažetak bude ograničen na selekciju, potreban je zaseban
  follow-up (nije eksplicitno traženo).
- "Trajno sačuvano" (korisnikov treći zahtjev) je već pokriveno postojećim
  `catalogs.user_feedback` mehanizmom + `_notify_auto_applied_tariffs` transparentnošću iz
  prethodnog fixa — nije dodavana nova perzistencija u ovoj izmjeni jer je već postojala.

## Potreban follow-up

- Ručni test na rebuildovanom `.exe`-u: selektovati 1-2 stavke, kliknuti "Provjeri",
  potvrditi da se dijalog/auto-apply odnose SAMO na te stavke i da se promjena upisuje u
  tačan red.
- Razmotriti da li i opšta validacija (`_on_validate_all`) treba selekcijsko filtriranje.

## Potrebna korisnička potvrda

- Da li ovaj fix rješava opisani problem u praksi (selektovati konkretnu stavku, provjeriti
  da se ispravan red mijenja nakon prihvatanja prijedloga).
