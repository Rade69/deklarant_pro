## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_faktura_characterization.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e6-create-adapter-audit.md` — aktivan; E7 je predložen kao rename-only nastavak.
- `docs/context/history.md` §125 — aktivan; potvrđuje da Tab i PDF export već idu preko javnog adaptera.

## GitNexus impact

Korišćen je `gitnexus-refactoring` workflow. Direktni `impact` alat nije bio izložen, pa je urađen fallback:

- `rg` inventar svih `_on_create_naimenovanja`, `_create_naimenovanja_from_draft` i `create_naimenovanja()` referenci
- ciljano čitanje interne implementacije i characterization testa
- `gitnexus_detect_changes` prije commita

Rizik je LOW/MEDIUM po prirodi simbola: metoda je aktivna, ali je promjena rename-only, javni API ostaje isti, a E6 je već uklonio direktne produkcione pozivaoce.

## Reprodukcija prije izmjene

Ovo je cleanup/refactor. Prije izmjene je potvrđeno:

- `FakturaView.create_naimenovanja()` delegira na `_on_create_naimenovanja`
- `FakturaTab.create_naimenovanja()` i PDF export već koriste javni adapter
- characterization test direktno poziva internu metodu radi očuvanja post-akcija

## Šta je urađeno

- `FakturaView._on_create_naimenovanja` preimenovan u `FakturaView._create_naimenovanja_from_draft`.
- `FakturaView.create_naimenovanja()` delegira na novo interno ime.
- Root/dist produkcioni fajlovi su poravnati.
- Logger tagovi u toj metodi ažurirani su na novo ime.
- Testovi koji direktno karakterišu internu metodu prebačeni su na novo ime.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

Staro ime je izgledalo kao Qt event handler, iako poslije E6 više nije direktni handler za Tab/PDF tokove. Novo ime bolje opisuje odgovornost metode i smanjuje kognitivni šum u `FakturaView`.

## Kako je urađeno

Preimenovanje je urađeno bez mijenjanja tijela metode. Nije mijenjan workflow servis, grupisanje, pre-flight, split draft logika, post-akcije ili učenje tarifa.

## Šta nije dirano

- Nije mijenjano tijelo kreiranja naimenovanja.
- Nije diran `CreateNaimenovanjaWorkflowService`.
- Nije diran `CreateNaimenovanjaService.create_smart_group()`.
- Nije diran `_on_import_finished_legacy`.
- Nije diran Agent pipeline osim postojećeg legacy fallback testa.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...`.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py tests/unit/test_faktura_characterization.py tests/unit/test_puna_auto_pipeline.py dist_client/tests/unit/test_puna_auto_pipeline.py`
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_characterization.py tests/unit/test_puna_auto_pipeline.py -q` → 64/64 passed
- `python -m pytest dist_client/tests/unit/test_puna_auto_pipeline.py -q` → 17/17 passed
- `rg` potvrda: nema `def _on_create_naimenovanja` u root/dist produkcionom kodu.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je promjena rename-only i testovi direktnih pozivalaca prolaze. Za svaku promjenu tijela ove metode i dalje je potreban poseban review.

## Pronađeni problemi

Preostale `_on_create_naimenovanja` reference postoje samo u legacy pipeline test stubu/assertima. To je namjeran test dokaza da se stari private fallback ne koristi.

## Odbačene opcije

- Odbačeno: mijenjati workflow ili post-akcije. Razlog: E7 je rename-only.
- Odbačeno: brisati legacy pipeline stub. Razlog: on štiti E1 pravilo da Agent pipeline bez javnog API-ja kontrolisano staje.

## Konflikti / kontradiktorni izvori

Nema konflikta u produkcionom kodu. E6 tvrdnja da se metoda ne smije brisati ostaje važeća: metoda nije obrisana, samo je preimenovana.

## Commitovi

| Hash | Poruka |
| --- | --- |
| af83bd9 | `refactor(faktura): preimenuj internu logiku kreiranja naimenovanja` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_view.py`, `test_faktura_controller.py` i `test_faktura_characterization.py` čitani su ciljano.

## Rizici / ograničenja

Nije rađen ručni GUI E2E za dugme “Kreiraj Naimenovanja” ili PDF export. Testovi štite adaptere, pipeline i karakterizaciju post-akcija.

## Potreban follow-up

Sljedeći mogući korak je E8: audit `_on_import_finished_legacy` i odluka da li ostaje dokumentovani fallback ili može dobiti neutralnije ime uz import workflow parity testove.

## Potrebna korisnička potvrda

Za E8 treba potvrditi da se ne dira import ponašanje, nego samo audit ili eventualno rename fallback metode.
