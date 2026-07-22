# Agent Report — 2026-07-22: Transparentnost za ODBIJENE istorijske prijedloge

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `services/agent/validation/historical_tariff_search_service.py` + `dist_client` kopija
- `gui/tabs/faktura_view.py` + `dist_client` kopija
- `tests/unit/test_faktura_view_auto_rejected_notice.py` (novo)
- `tests/unit/test_faktura_view_provjeri_selekcija.py` (dopuna, 3 nova testa)
- `tests/unit/test_historical_tariff_validation.py` (dopuna postojećeg testa)
- `project_rooms/2026-07-22_transparentnost-odbijenih-prijedloga.md` (plan, HIGH impact)
- `docs/CONTEXT.md` (§39)

## Status izvora

Posljednja od "sitnih stvari" koje je korisnik zatražio da se riješe dok Codex nastavlja
svoj dio posla. Poznat otvoren follow-up iz `agent_reports/
2026-07-21_transparentnost-auto-primijenjenih-tarifa.md`: "Reject-feedback grana i dalje
ostaje potpuno tiha — ako korisnik želi istu transparentnost i za odbijene prijedloge, to je
zaseban follow-up." Danas eksplicitno zatraženo.

## GitNexus impact

`HistoricalTariffSearchService.validate_lines` — **HIGH** (30 impactedCount, transitivno kroz
`chat_intent_handler._prikaz_tarifnih_trenutnih`, `scripts/agent_tariff_eval_report.py`,
`FakturaView._on_validate_all`/`_on_import_finished`/`_process_batch_records`). Po AGENTS.md
pravilu, napisan `project_rooms/2026-07-22_transparentnost-odbijenih-prijedloga.md` PRIJE
izmjene. Mitigacija: dodaje se NOVI instance atribut `self.last_auto_rejected` (analogan
postojećem `last_auto_applied`) — POVRATNA VRIJEDNOST metode (`results` lista) i njen potpis
ostaju POTPUNO nepromijenjeni, funkcionalno nulti rizik za sve postojeće pozivaoce (nijedan
danas ne čita `last_auto_rejected`). `gitnexus_detect_changes()` nakon izmjene:
`risk_level: low`, `affected_count: 0`.

## Šta je urađeno

1. `HistoricalTariffSearchService.__init__`: dodat `self.last_auto_rejected: list[tuple[int,
   str]] = []`.
2. `validate_lines()`: resetuje `self.last_auto_rejected = []` na početku (kao
   `last_auto_applied`); u `feedback_action == "reject"` grani sad radi
   `self.last_auto_rejected.append((idx, best.tarifni_broj_historijski))` prije `continue`.
3. `FakturaView._run_historical_tariff_validation`: dohvata `auto_rejected = getattr(svc,
   'last_auto_rejected', [])`, remapira indekse (isti obrazac kao `auto_applied` kad je
   `row_indexes is not None`), i poziva novu `_notify_auto_rejected_tariffs(auto_rejected)`
   kad `not auto` i ima odbijenih stavki (u `auto=True` modu samo loguje).
4. Nova `_notify_auto_rejected_tariffs()` metoda — simetrična sa
   `_notify_auto_applied_tariffs()`, navodi Rb./naziv/"bio bi predložen: TARIF" i eksplicitno
   objašnjava da je razlog ranija ručna odluka "Odbij".
5. Generalna "nema boljeg prijedloga" poruka (kad je `matches` prazno) se sad suprimira i
   kad postoji `auto_rejected` (ne samo `auto_applied`) — specifičnija poruka je tačnija.

## Zašto je urađeno

Bez ove izmjene, ranija ODBIJENA odluka (ispravna ili pogrešna) bi se tiho ponavljala
zauvijek bez ikad ponovnog pregleda — identičan mehanizam entrenchmenta kao i kod
"prihvaćenih" prijedloga prije §27 dopune 2 fixa, samo u suprotnom smjeru. Korisnik mora
znati DA je nešto preskočeno i ZAŠTO, da bi mogao promijeniti mišljenje ako je ranija odluka
bila pogrešna.

## Kako je urađeno

Identičan kod-obrazac kopiran iz postojeće `auto_applied` transparentnosti (isti remapping
lanac, ista `_show_scrollable_info_dialog` struktura) — bez izmišljanja nove logike.
`dist_client` kopije oba fajla bile su identične root-u prije izmjene (potvrđeno diff-om) —
izmjene primijenjene identično na oba mjesta, `diff` nakon izmjene potvrđuje 0 razlike.

## Šta nije dirano

- `_feedback_action()`, `tariff_feedback_service.py`, `user_feedback` tabela — logika
  odlučivanja accept/reject nije mijenjana, samo je dodata VIDLJIVOST postojeće odluke.
- `_notify_auto_applied_tariffs()` — netaknuta, nova metoda je potpuno zasebna.
- Povratna vrijednost `validate_lines()` — identična za sve postojeće pozivaoce.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_provjeri_selekcija.py
  tests/unit/test_faktura_view_auto_rejected_notice.py
  tests/unit/test_historical_tariff_validation.py -v
  → 44 passed (9 novih/dopunjenih ovim zadatkom + 35 postojećih nepromijenjenih)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 859 passed, 58 skipped, 3 failed, 1 error (identično pretpostojećim/nepovezanim
    failovima iz prethodnih izvještaja)
python -m py_compile [4 izmijenjena .py fajla] → OK
diff (root vs dist_client, oba fajla) → 0 linija razlike
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

Napomena tokom pisanja testova: postojeći MagicMock-bazirani testovi u
`test_faktura_view_provjeri_selekcija.py` nisu eksplicitno postavljali
`svc_instance.last_auto_rejected` — MagicMock-ov default `__iter__`/`__len__`/`__bool__`
ponašanje je slučajno spriječilo padove (prazna iteracija, `len()=0`), ali je to bio
neeksplicitan test-artefakt, ne stvarna garancija. Svi postojeći testovi u tom fajlu
eksplicitno dopunjeni sa `svc_instance.last_auto_rejected = []` radi jasnoće i determinizma.

## Pronađeni problemi

Test-mock krhkost opisana gore (riješeno dopunom, ne utiče na produkcioni kod — u praksi je
`svc` uvijek pravi `HistoricalTariffSearchService` sa ispravno inicijalizovanim atributom).

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | feat(tarifa): transparentnost za ranije odbijene istorijske prijedloge |

## Rizici / ograničenja

- Isti rizik kao kod `_notify_auto_applied_tariffs` (dokumentovan u ranijem izvještaju):
  poruka se prikazuje svaki put kad postoji odbijena stavka u interaktivnom modu — ako se
  ovo dešava često na istoj fakturi, može postati zamorno. Nije optimizovano (npr. "ne
  prikazuj ponovo za ovu sesiju").

## Potreban follow-up

- Ručni test u aplikaciji: potvrditi da se poruka za odbijene prijedloge pojavljuje ispravno
  i da se generalna "nema prijedloga" poruka ne prikazuje duplo.

## Potrebna korisnička potvrda

- Da li je poruka za odbijene prijedloge dovoljno jasna i ne suviše nametljiva u praksi.
