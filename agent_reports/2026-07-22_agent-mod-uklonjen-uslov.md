# Agent Report — 2026-07-22: Uklonjen pogrešan agent_mode uslov za auto-provjeru

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + `dist_client` kopija
- `tests/unit/test_faktura_view_provjeri_nakon_uvoza.py` (izmijenjeno)
- `docs/CONTEXT.md` (korekcija §30)

## Status izvora

Direktan nastavak `agent_reports/2026-07-22_provjeri-automatski-nakon-uvoza.md` (isti dan).
Korisnik je odmah testirao rebuildovani `.exe` i prijavio da je nakon uvoza kroz agent mod
dobio POTPUNU TIŠINU (ni dijalog ni obavještenje), tek nakon ručne selekcije+klika na
"Provjeri" je dobio ispravan prijedlog (21069098 za SUSSINA — potvrđujući da je supplier
filter fix iz §29 ispravan).

## GitNexus impact

`_on_import_finished`/`_process_batch_records` — LOW (isto kao u prethodnom izvještaju istog
dana, potpisi metoda nepromijenjeni). `gitnexus_detect_changes()`: `risk_level: low`,
`affected_count: 0`.

## Šta je urađeno

Prethodna izmjena (isti dan) je uslovila automatski poziv sa `if not self._agent_mode:`,
pod pretpostavkom da agent mod uvijek ima svoj naknadni poziv provjere preko pune
automatizacije. Pogrešno: `ImportPipelineService` ima TRI odvojene agent rute uvoza
("Analiza", "Uvezi u deklaraciju", "Puna automatizacija") — `self._agent_mode` je aktivan za
SVE tri, ali SAMO "Puna automatizacija" (`_puna_auto_pipeline`) ima naknadni
`_on_validate_all(auto=True)` poziv u svom koraku 3. Korisnik je uvezao fakturu kroz agent
mod (potvrdio: "Uvezao sam je kroz agentski mod") — vjerovatno rutu "Uvezi u deklaraciju",
koja NEMA taj naknadni poziv — pa je provjera bila trajno preskočena bez alternative.

Fix: uklonjen `if not self._agent_mode:` uslov u oba mjesta (`_on_import_finished`,
`_process_batch_records`) — poziv `self._run_historical_tariff_validation(auto=False)` se
sad izvršava UVIJEK nakon uvoza, bez obzira na agent mod.

## Zašto je urađeno

Analizom `import_pipeline_service.py` potvrđeno: `_puna_auto_pipeline` NE uvozi fajlove sam
— radi na VEĆ postojećem `ctrl.draft.invoice_lines` (prvi korak mu je "Izračunaj mase", što
pretpostavlja da su stavke već uvezene). Pipeline se pokreće ODVOJENO i KASNIJE, tipično kroz
posebnu chat komandu ("uradi sve") NAKON što je uvoz već završen (i `_on_import_finished` već
odavno izvršen). Dakle nema stvarnog VREMENSKOG preklapanja između mog eager poziva (na
uvozu) i pipeline-ovog kasnijeg poziva — a čak i kad bi se oba desila, pipeline-ov poziv je
`auto=True` (tih, samo log), pa ne bi prikazao duplikat dijaloga. Originalni strah od
"dupliranja/prekidanja" pipeline-a je bio neosnovan.

## Kako je urađeno

Uklonjen `if not self._agent_mode:` wrapper na oba mjesta — poziv ostaje identičan
(`self._run_historical_tariff_validation(auto=False)`), samo bez uslova. Komentari ažurirani
da objasne ZAŠTO nema uslova (umjesto da objašnjavaju zašto GA IMA, kao ranije) — uključujući
eksplicitnu napomenu za buduće agente da `self._agent_mode` nije pouzdan proxy za "pipeline
će ovo kasnije sam odraditi".

`dist_client` kopija ažurirana identično na oba mjesta.

## Šta nije dirano

- `_puna_auto_pipeline`/`import_pipeline_service.py` — nula izmjena, ostaje potpuno
  nepromijenjen. Njegov `auto=True` poziv i dalje radi tiho, kao i prije.
- Supplier filter fix (§29) — potvrđen da radi ispravno (korisnik je vidio 21069098 predlog
  nakon ručnog "Provjeri" klika), nije ponovo diran.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -v
  → 4 passed (ažurirano: sad svi testovi očekuju poziv i sa i bez agent_mode)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 846 passed, 58 skipped, 3 failed, 1 error (isti pretpostojeći/nepovezani failovi)
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py → OK
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

Nema novih van onoga što je već ispravljeno.

## Konflikti / kontradiktorni izvori

Ova izmjena direktno ISPRAVLJA pogrešnu pretpostavku iz `agent_reports/
2026-07-22_provjeri-automatski-nakon-uvoza.md` (isti dan, ranije danas) — taj izvještaj
tretirati kao DJELIMIČNO zastario u dijelu koji opisuje "agent mod izuzetak" (Šta je
urađeno/Rizici sekcije); CONTEXT.md §30 eksplicitno dokumentuje i staru pretpostavku i
korekciju radi transparentnosti.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | fix(faktura): ne preskaci provjeru tarifa nakon uvoza u agent modu |

## Rizici / ograničenja

- Sad se provjera pokreće u SVAKOJ agent ruti uvoza (Analiza/Uvezi/Puna automatizacija) —
  ako "Puna automatizacija" ruta uvozi VIŠE fajlova u brzoj sukcesiji prije nego što stigne
  do svog koraka 3, moguće je da se eager dijalog pojavi VIŠE puta (jednom po fajlu) prije
  nego pipeline uopšte krene. Nije primijećeno kao problem u ovoj sesiji, ali vrijedi pratiti.

## Potreban follow-up

- Ručni test: uvoz kroz agent mod (istu rutu koju je korisnik koristio) treba sad pokazati
  dijalog automatski, bez potrebe za ručnim "Provjeri" klikom.
- Rebuild `.exe`-a za sledeći test ciklus.

## Potrebna korisnička potvrda

- Da li se dijalog sad pojavljuje automatski nakon uvoza kroz agent mod.
