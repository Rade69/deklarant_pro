## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_import_workflow_parity.py`
- `dist_client/tests/unit/test_import_workflow_parity.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e6-create-adapter-audit.md` — aktivan; `_on_import_finished_legacy` je bio označen kao aktivan fallback, ne kandidat za brisanje.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e7-create-rename.md` — aktivan; predložio E8 audit import fallback metode.

## GitNexus impact

Korišćen je `gitnexus-refactoring` workflow. Direktni `impact` alat nije bio izložen, pa je urađen fallback:

- `rg` inventar `_on_import_finished`, `_on_import_finished_legacy`, `_finish_import_legacy_path`, `_can_use_unified_manual_import`
- ciljano čitanje import fallback metode i import workflow parity testa
- `gitnexus_detect_changes` prije commita

Rizik je LOW/MEDIUM: import put je važan, ali promjena je rename-only i pokrivena import workflow parity testovima.

## Reprodukcija prije izmjene

Ovo je cleanup/refactor. Prije izmjene je potvrđeno:

- `_on_import_finished` je Qt slot spojen na `import_worker.finished`
- kada unified manual import nije moguć, delegira na `_on_import_finished_legacy`
- import workflow parity test potvrđuje da unified put ne poziva legacy fallback

## Šta je urađeno

- `FakturaView._on_import_finished_legacy` preimenovan u `FakturaView._finish_import_legacy_path`.
- `_on_import_finished` sada delegira na novo interno ime.
- Root/dist produkcioni fajlovi su poravnati.
- Root/dist import workflow parity testovi ažurirani su na novo ime.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

Staro ime je izgledalo kao drugi Qt event handler, iako je metoda fallback implementation path. Novo ime jasnije kaže da je riječ o legacy putanji završetka importa.

## Kako je urađeno

Preimenovanje je urađeno bez promjene tijela fallback metode. Nije mijenjan unified import workflow niti uslovi za fallback.

## Šta nije dirano

- Nije mijenjano ponašanje `_on_import_finished`.
- Nije mijenjan `_can_use_unified_manual_import`.
- Nije mijenjana legacy import logika.
- Nije mijenjan batch import.
- Nije mijenjana EUR.1/PE logika, težine ili history validation poslije uvoza.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...`.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_import_workflow_parity.py dist_client/tests/unit/test_import_workflow_parity.py tests/unit/test_faktura_characterization.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py`
- `python -m pytest tests/unit/test_import_workflow_parity.py tests/unit/test_faktura_characterization.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -q` → 41/41 passed
- `python -m pytest dist_client/tests/unit/test_import_workflow_parity.py dist_client/tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -q` → 28/28 passed
- `rg` potvrda: nema `def _on_import_finished_legacy` u root/dist produkcionom kodu.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je promjena rename-only i import parity testovi prolaze. Za promjenu tijela import fallback-a potreban je poseban review.

## Pronađeni problemi

Nema novih problema. `_on_import_finished` ostaje ispravno imenovan jer je stvarni Qt slot.

## Odbačene opcije

- Odbačeno: preimenovati `_on_import_finished`. Razlog: to je stvarni slot za `import_worker.finished`.
- Odbačeno: ukloniti legacy fallback. Razlog: fallback je i dalje aktivan kada unified manual import nije dostupan.

## Konflikti / kontradiktorni izvori

Nema konflikta u produkcionom kodu. E6 tvrdnja da fallback nije za brisanje ostaje važeća: nije obrisan, samo preimenovan.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 8b134e6 | `refactor(faktura): preimenuj legacy import fallback` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_view.py` i import workflow parity testovi čitani su ciljano.

## Rizici / ograničenja

Nije rađen ručni GUI uvoz stvarne fakture. Verifikacija je kroz import workflow parity i characterization testove.

## Potreban follow-up

Sljedeći korak može biti završni E-cleanup audit: pretražiti preostale `_on_*` metode u Faktura sloju i razdvojiti stvarne Qt slotove od internih metoda koje su još kandidati za neutralnija imena.

## Potrebna korisnička potvrda

Nema dodatne potvrde za E8. Za uklanjanje legacy fallback-a potrebna je posebna poslovno-tehnička odluka nakon dokaza da unified import pokriva sve slučajeve.
