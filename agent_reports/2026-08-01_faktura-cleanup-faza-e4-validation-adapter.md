## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e2-dead-code-audit.md` — aktivan; upozorava da `_on_validate_all` nije za brisanje.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e3-wrapper-cleanup.md` — aktivan; predložio E4 kao sljedeći uski korak.

## GitNexus impact

Korišćen je `gitnexus-refactoring` workflow. Direktni `impact` alat nije bio izložen, pa je urađen fallback:

- `rg` inventar poziva `validate()`, `_on_validate_all` i `validate_requested`
- ciljano čitanje `FakturaTab.validate`
- `gitnexus_detect_changes` prije commita

Rizik je LOW: izmjena mijenja samo adapter poziv u Tab sloju, a javni `FakturaView.validate()` već delegira na istu `_on_validate_all` implementaciju.

## Reprodukcija prije izmjene

Ovo nije bugfix nego cleanup/refactor. Prije izmjene je potvrđeno da `FakturaTab.validate(auto=True)` direktno poziva `self.view._on_validate_all(auto=True)`.

## Šta je urađeno

- `FakturaTab.validate(auto=True)` sada poziva `self.view.validate(auto=True)`.
- Ista izmjena preslikana u `dist_client/gui/tabs/faktura_tab.py`.
- Test `test_faktura_tab_validate_auto_uses_view_validation_adapter` sada stvarno monkeypatchuje javni `view.validate`.
- Komentar u root/dist `faktura_view.py` ažuriran da opisuje javni `validate(auto=True)` tok.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

E4 smanjuje direktne private View zavisnosti u Tab sloju, ali ne dira osjetljivu validacionu implementaciju. To je mali, reverzibilan korak prema čistijem 3-layer obrascu.

## Kako je urađeno

Promjena je jedan adapter poziv: umjesto direktnog `_on_validate_all(auto=True)`, Tab koristi postojeći javni `validate(auto=True)`.

## Šta nije dirano

- Nije brisan niti preimenovan `FakturaView._on_validate_all`.
- Nije mijenjan ručni `validate_requested` signalni tok.
- Nije mijenjana logika validacije, bojenja redova, istorijske validacije ili `blockSignals`.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...`.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_tab.py dist_client/gui/tabs/faktura_tab.py gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py`
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` → 51/51 passed
- `rg` potvrda: `FakturaTab.validate(auto=True)` više ne poziva `_on_validate_all` direktno.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je izmjena LOW risk i ograničena na adapter poziv. Za sljedeću fazu koja bi dirala `_on_validate_all` ime ili granice treba novi audit/checker.

## Pronađeni problemi

Nema novih funkcionalnih problema. Pronađen je samo zastario komentar u `faktura_view.py` koji je pominjao stari private auto-validacioni naziv; ažuriran je u root i dist kopiji.

## Odbačene opcije

- Odbačeno: preimenovati ili brisati `_on_validate_all` u E4. Razlog: E2 ga je potvrdio kao aktivan implementation path.
- Odbačeno: mijenjati ručni signalni tok validacije. Razlog: nije u E4 scope-u i već ima testove za `blockSignals`.

## Konflikti / kontradiktorni izvori

Nema konflikata u produkcionom kodu. E2/E3 reportovi su usklađeni sa ovom izmjenom.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 14135df | `refactor(faktura): koristi javni adapter validacije` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_tab.py`, relevantni dio `faktura_view.py` i `test_faktura_controller.py` čitani su ciljano.

## Rizici / ograničenja

E4 ne uklanja `_on_validate_all`; samo uklanja direktnu Tab zavisnost od njega. Sljedeće eventualno preimenovanje validacione implementacije zahtijeva poseban audit selekcijskih testova.

## Potreban follow-up

Sljedeći mogući korak je E5: audit/preimenovanje `_on_validate_all` u neutralnije interno ime, ali samo ako se potvrdi da selekcijski testovi i ručni `validate_requested` tok ostaju netaknuti.

## Potrebna korisnička potvrda

Za samo E4 nema dodatne potvrde. Za E5 treba potvrditi da prihvatamo preimenovanje aktivne interne validacione metode, ne brisanje.
