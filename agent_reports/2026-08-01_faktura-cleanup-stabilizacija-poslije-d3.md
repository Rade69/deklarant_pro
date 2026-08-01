## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py` / `dist_client/gui/tabs/faktura_view.py` — read-only/paritet provjera
- `services/faktura/create_naimenovanja_workflow_service.py` / `dist_client/services/faktura/create_naimenovanja_workflow_service.py` — read-only/paritet provjera
- `services/faktura/models.py` / `dist_client/services/faktura/models.py` — read-only/paritet provjera
- `tests/unit/test_faktura_create_naimenovanja_workflow_service.py`
- `tests/unit/test_faktura_characterization.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_puna_auto_pipeline.py`
- XML/ASYCUDA testovi navedeni u verifikaciji
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije stabilizacije.
- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md` — aktivan; stabilizacija je preduslov za završnu Fazu E.
- `agent_reports/2026-07-30_faktura-cleanup-faza-d1-create-naimenovanja-core-service.md` — aktivan.
- `agent_reports/2026-07-30_faktura-cleanup-faza-d2-create-naimenovanja-post-actions.md` — aktivan.
- `agent_reports/2026-07-30_faktura-cleanup-faza-d3-create-naimenovanja-priprema-poruke.md` — aktivan.

## GitNexus impact

Nije bilo izmjena produkcionog koda, pa nije rađen novi pre-change impact za simbol. Stabilizaciona faza je koristila read-only grep pozivalaca i test kapije. Prije commita dokumentacije potrebno je pokrenuti `gitnexus_detect_changes(scope="staged")`; očekivani scope su samo `docs/context/history.md` i ovaj report.

## Reprodukcija prije izmjene

Ovo nije bugfix nego stabilizacioni audit poslije refaktora. Reprodukcija nije primjenjiva; dokaz je kombinacija paritet provjera, grep pozivalaca i testova.

## Šta je urađeno

- Potvrđen root/dist_client paritet za tri D1-D3 fajla.
- Pregledani pozivaoci `Kreiraj Naimenovanja` toka.
- Potvrđeno da ručni toolbar ide preko signala i javnog adaptera.
- Potvrđeno da Agent pipeline prvo koristi `create_naimenovanja(auto=True)`, a tek zatim privatni `_on_create_naimenovanja` fallback.
- Pokrenute tri test kapije: ciljano create/pipeline, širi Faktura/Agent set i XML/ASYCUDA smoke set.
- Dopunjen `docs/context/history.md` zapisom stabilizacije.

## Zašto je urađeno

Cleanup D1-D3 dira najosjetljiviji Faktura workflow. Prije Faze E, gdje se planira precizno brisanje fallback/legacy koda, treba dokazati da postojeći behavior još stoji i jasno izdvojiti šta je automatizovano pokriveno, a šta traži ručnu GUI potvrdu korisnika.

## Kako je urađeno

Korišćeni su `git diff --no-index` za root/dist_client paritet, `rg` za pozivaoce i postojeći pytest setovi. Nije mijenjan produkcioni kod.

## Šta nije dirano

- Nije brisan nijedan fallback.
- Nije mijenjan `FakturaView._on_create_naimenovanja`.
- Nije mijenjan `FakturaTab.create_naimenovanja`.
- Nije mijenjan Agent pipeline.
- Nije mijenjan XML exporter.
- Nisu dirane tuđe WIP izmjene u working tree-u.

## Verifikacija

- `git diff --no-index -- gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py` → bez razlike
- `git diff --no-index -- services/faktura/create_naimenovanja_workflow_service.py dist_client/services/faktura/create_naimenovanja_workflow_service.py` → bez razlike
- `git diff --no-index -- services/faktura/models.py dist_client/services/faktura/models.py` → bez razlike
- `python -m py_compile services/faktura/models.py services/faktura/create_naimenovanja_workflow_service.py gui/tabs/faktura_view.py dist_client/services/faktura/models.py dist_client/services/faktura/create_naimenovanja_workflow_service.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py`
- `python -m pytest tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_characterization.py tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py tests/unit/asycuda_item_limit_test.py -q` → 78 passed
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_auto_fill_workflow_service.py tests/unit/test_faktura_mass_workflow_service.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_mapping_service.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py tests/unit/asycuda_item_limit_test.py -q -m "not integration"` → 172 passed
- `python -m pytest tests/unit/test_asycuda_goods_description.py tests/unit/test_asycuda_helpers.py tests/unit/test_safe_xml.py tests/unit/test_parse_naimenovanja_xml.py tests/unit/test_agent_v2_wiring_fixes.py tests/integration/test_decision_xml_preflight.py tests/integration/test_decision_to_naimenovanja.py -q` → 126 passed

## Nezavisna provjera

Nije rađena posebna checker sesija jer nije bilo produkcionih izmjena koda. Za Fazu E preporučena je najmanje jedna nezavisna provjera diff-a prije brisanja fallback-a, jer se tada mijenja runtime površina.

## Pronađeni problemi

- `rg` potvrđuje da privatni `_on_create_naimenovanja` još ima fallback poziv iz Agent pipeline-a i direktan poziv iz PDF export helper toka. To nije regresija; to je eksplicitno kandidat za Fazu E, nakon korisničkog E2E.
- Working tree sadrži tuđe WIP izmjene (`dist_client/ui/...`, untracked fajlovi); nisu dirane.

## Odbačene opcije

- Odbačeno: odmah brisati `_on_create_naimenovanja` ili Agent fallback u ovoj fazi. Razlog: stabilizacija treba da bude dokazna faza bez behavior promjene; brisanje pripada Fazi E.
- Odbačeno: pokretati cijeli `tests/` suite. Razlog: za ovu fazu jači dokaz po scope-u je ciljano pokrivanje create/pipeline + XML/ASYCUDA; cijeli suite može uključiti spore/DB zavisne testove nepovezane sa D1-D3.

## Konflikti / kontradiktorni izvori

Nema kontradikcija. Manifest kaže da se fallback briše tek nakon stabilizacije i korisničkog E2E; ova faza potvrđuje automatizovani dio, ali ručni GUI E2E još nije urađen.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `docs(faktura): dokumentuj stabilizaciju poslije d3` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti jer je obavezan i kratak evergreen fajl.
- `docs/context/history.md` nije čitan cijeli; pregledan je samo kraj fajla radi numeracije nove sekcije.
- Veliki produkcioni fajlovi nisu čitani cijeli; korišćeni su grep/paritet/testovi.

## Rizici / ograničenja

Automatizovani testovi ne dokazuju stvarni Windows GUI prikaz, modal fokus, realan izbor korisnika u preflight/split dijalogu niti stvarni XML export kroz klik. To mora potvrditi korisnik prije Faze E.

## Potreban follow-up

Sljedeća faza je korisnički live E2E ili, ako korisnik prihvati ograničenje, Faza E sa jako uskim scope-om: prvo identifikacija i uklanjanje samo sigurnih fallback poziva.

## Potrebna korisnička potvrda

Prije Faze E korisnik treba ručno potvrditi:

1. uvoz realne fakture;
2. izračun masa;
3. auto-fill/validacija;
4. ručni `Kreiraj Naimenovanja`;
5. pregled Naimenovanja taba;
6. pregled Zaglavlje taba;
7. XML export smoke test.
