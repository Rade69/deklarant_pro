# Faktura završni E-cleanup audit

## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_controller.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_controller.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `dist_client/tests/unit/test_puna_auto_pipeline.py`
- `docs/context/history.md`

## Status izvora

Aktivni izvori:

- `docs/context/history.md` sekcije 121-127 — hronologija E1-E8 cleanup faza.
- Trenutni kod u root i `dist_client` Faktura sloju.
- Trenutni pipeline testovi koji namjerno čuvaju legacy private stubove radi dokazivanja da ih Agent pipeline ne koristi.

## GitNexus impact

Nije rađena produkciona izmjena simbola. Audit je bio read-only nad kodom, uz dokumentacioni zapis rezultata.

## Reprodukcija prije izmjene

Ovo nije bugfix nego završni cleanup audit. Provjera je urađena ciljanim `rg` upitima:

- inventar svih `def _on_` metoda u root Faktura sloju;
- inventar svih `def _on_` metoda u `dist_client` Faktura sloju;
- pretraga starih privatnih naziva: `_on_calculate_masses`, `_on_auto_fill`, `_on_validate_all`, `_on_create_naimenovanja`, `_on_import_finished_legacy`;
- provjera javnih adaptera i novih internih naziva: `validate`, `create_naimenovanja`, `calculate_masses`, `auto_fill`, `_validate_all_items`, `_create_naimenovanja_from_draft`, `_finish_import_legacy_path`.

## Šta je urađeno

Potvrđeno je da su E3-E8 cleanup faze uklonile ili preimenovale stare private View nazive iz produkcionog runtime koda:

- `FakturaView._on_calculate_masses` — uklonjen;
- `FakturaView._on_auto_fill` — uklonjen;
- `FakturaView._on_validate_all` — preimenovan u `_validate_all_items`;
- `FakturaView._on_create_naimenovanja` — preimenovan u `_create_naimenovanja_from_draft`;
- `FakturaView._on_import_finished_legacy` — preimenovan u `_finish_import_legacy_path`.

Potvrđeno je da root i `dist_client` imaju isti inventar preostalih Faktura `_on_*` metoda.

## Zašto je urađeno

E-cleanup je imao cilj da ukloni naslijeđene private entry pointe koji su ostali poslije stvarne 3-layer migracije Faktura taba. Završni audit je potreban da se ne nastavi sa mehaničkim brisanjem metoda koje, iako imaju `_on_*` ime, predstavljaju stvarne Qt slotove ili signal handlere.

## Kako je urađeno

Audit je urađen ciljanim pretragama umjesto čitanja cijelog velikog `faktura_view.py` fajla:

- `rg -n "^\s+def _on_" ...` nad root fajlovima;
- isti upit nad `dist_client` fajlovima;
- `rg` pretraga starih privatnih naziva nad `gui`, `dist_client/gui`, `tests/unit`, `dist_client/tests/unit`;
- `rg` pretraga javnih adaptera i novih internih metoda.

## Šta nije dirano

- Nije diran produkcioni Python kod.
- Nisu dirani postojeći WIP fajlovi drugih agenata u working tree-u.
- Nisu brisani pipeline test stubovi sa starim private imenima, jer su namjerni dokaz da se legacy fallback ne koristi.
- Nisu refaktorisani import/export Qt handleri; to bi bila nova faza, ne završni E-cleanup.

## Verifikacija

Verifikacija je read-only audit:

- root i `dist_client` `def _on_` inventari su u paritetu;
- stari private nazivi više nisu definisani u produkcionom `faktura_view.py`;
- preostala pojavljivanja starih naziva su u signal handlerima `*_requested` ili u namjernim pipeline test stubovima;
- javni adapteri `validate`, `create_naimenovanja`, `calculate_masses` i `auto_fill` postoje u root i `dist_client` sloju.

Test suite nije pokretan jer nije bilo produkcionih code izmjena.

## Nezavisna provjera

Nije rađena u ovom koraku. Pošto nije bilo produkcionih code izmjena, nezavisni checker nije obavezan. Ako se otvori nova faza dubljeg import/export refaktora, treba je tretirati kao zaseban refactor sa standardnim review/test gate-om.

## Pronađeni problemi

Nije pronađen dodatni siguran E-cleanup kandidat. Preostali `_on_*` nazivi nisu svi tehnički dug:

- `FakturaTab._on_*_requested` metode su Controller signal handleri;
- `FakturaView._on_import_finished`, `_on_import_error`, `_on_export_*`, `_on_batch_*`, `_on_selection_changed` i slične metode su stvarni UI/Qt handleri;
- lokalni `_on_accepted` callback u modalnom toku je lokalna callback funkcija, ne javni private API.

## Odbačene opcije

Mehaničko preimenovanje svih preostalih `_on_*` metoda je odbačeno. Razlog: većina su stvarni Qt slotovi ili event handleri, pa bi takav cleanup povećao rizik bez jasne koristi.

## Konflikti / kontradiktorni izvori

Nema kontradikcija. `docs/context/history.md` sekcije E2-E8 i trenutni kod se poklapaju: ono što je ranije označeno kao aktivni path sada je ili preimenovano u neutralan interni naziv ili ostavljeno kao stvarni Qt handler.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `docs(faktura): dokumentuj zavrsni e cleanup audit` |

## Kontekst korišćen

- `docs/context/history.md` sekcije 121-127, zbog kontinuiteta E-cleanup faza.
- Ciljani `rg` inventar Faktura root/dist metoda, umjesto potpunog čitanja velikog `faktura_view.py`.

## Rizici / ograničenja

Audit potvrđuje samo stanje naziva i entry pointa. Ne tvrdi da je kompletan import/export UI sloj arhitekturno idealan; tvrdi da u okviru E-cleanup-a nema više sigurnog mehaničkog brisanja bez otvaranja nove refactor faze.

## Potreban follow-up

Ako se želi nastaviti čišćenje Faktura taba, sljedeći prirodni korak je nova faza za dublji import/export handler refactor, sa posebnim planom, test gate-om i root/dist paritetom.

## Potrebna korisnička potvrda

Nema obavezne potvrde za ovaj audit. Korisnik može odlučiti da li želi novu fazu za import/export handler refactor.
