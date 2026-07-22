# Agent Report — 2026-07-22: Agent uvoz — treći, potpuno odvojen kod-put za "auto nakon uvoza"

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/agent/agent_controller.py` + `dist_client` kopija
- `tests/unit/test_agent_controller_provjeri_nakon_uvoza.py` (novo)
- `docs/CONTEXT.md` (§31, nastavak §30)

## Status izvora

Direktan nastavak `agent_reports/2026-07-22_agent-mod-uklonjen-uslov.md` (isti dan). Korisnik
je testirao rebuild i i dalje dobio potpunu tišinu nakon agent uvoza — tek ručni klik
"Provjeri" je dao ispravan rezultat (21069098 za SUSSINA, potvrđujući §29 fix i dalje radi).

## GitNexus impact

`AgentController._on_all_completed` — LOW (0 direktnih pozivalaca u grafu, Qt signal
handler; 0 affected_processes). `gitnexus_detect_changes()` nakon izmjene: `risk_level: low`,
`affected_count: 0`.

## Šta je urađeno

Praćenjem `_load_data_from_draft()` poziva kroz cijeli kod otkriveno: agent uvoz (bilo koja
od tri agent rute — "Analiza", "Uvezi u deklaraciju", "Puna automatizacija") NE ide kroz
`FakturaView._on_import_finished`/`_process_batch_records` (Qt signal handleri vezani na
obični GUI `ImportWorker`) — ide kroz potpuno ODVOJEN kod-put,
`AgentController._on_all_completed`, koji sam direktno puni `self.draft.invoice_lines` i
poziva `fw._load_data_from_draft()`. §30-ov fix (uklanjanje `self._agent_mode` uslova iz
`_on_import_finished`/`_process_batch_records`) je bio ispravan potez, ali NEDOVOLJAN — te
dvije funkcije se NIKAD nisu izvršavale za agent uvoz uopšte, bez obzira na bilo kakav uslov
unutra njih.

`_on_all_completed` završava obradu granom po `self._current_mode`:
- `"Puna automatizacija"` → zove `self._puna_auto_pipeline(...)`, koji u koraku 3 (mase →
  auto-popuna → validacija) zove `_on_validate_all(auto=True)` — tih, samo log.
- `else` (sve ostale agent rute, uklj. "Uvezi u deklaraciju" — rutu koju je korisnik stvarno
  koristio) — NIJE imala baš ništa vezano za tarifnu provjeru.

Dodat poziv u `else` granu: `if fw and hasattr(fw, '_run_historical_tariff_validation'):
fw._run_historical_tariff_validation(auto=False)`, odmah nakon
`self.workflow.transition(WorkflowState.COMPLETED)`.

## Zašto je urađeno

Ovo je JEDINO mjesto gdje se obrada za "Uvezi u deklaraciju" rutu završava — draft je već
popunjen (`self.draft.invoice_lines` sadrži sve procesirane linije), tabela je već osvježena
(`fw._load_data_from_draft()` je već pozvan par linija ranije), i korisnik je upravo prebačen
na Faktura tab da vidi rezultat — prirodan trenutak da se odmah pokrene i istorijska tarifna
provjera, tačno kako je korisnik tražio.

## Kako je urađeno

Jedan `if` blok dodat direktno u postojeći `else` ogranak (mutually exclusive sa "Puna
automatizacija" granom preko `if/else`) — nema rizika od duplikata jer se grane međusobno
isključuju. `dist_client` kopija bila je identična root-u (diff prije izmjene: 0 linija
razlike) — izmjena primijenjena identično, `diff` nakon izmjene: 0 linija razlike.

## Šta nije dirano

- `_puna_auto_pipeline`/`import_pipeline_service.py` — nula izmjena.
- `FakturaView._on_import_finished`/`_process_batch_records` (§30 fix) — ostaju kako jesu,
  i dalje ispravno pokrivaju OBIČAN (ne-agent) GUI import.
- `_analiza_pipeline` (Analiza mod bez uvoza u draft) — vraća se rano prije nego stigne do
  ove grane, ne dira se, nema šta provjeravati (nema draft izmjene).

## Verifikacija

```
python -m pytest tests/unit/test_agent_controller_provjeri_nakon_uvoza.py -v
  → 2 passed (novo): "Uvezi u deklaraciju" dobija poziv, "Puna automatizacija" ne duplira
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 848 passed, 58 skipped, 3 failed, 1 error (isti pretpostojeći/nepovezani failovi)
python -m py_compile gui/tabs/agent/agent_controller.py dist_client/gui/tabs/agent/agent_controller.py → OK
diff (root vs dist_client) → 0 linija razlike (identični i prije i poslije izmjene)
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

Aplikacija ima NAJMANJE TRI odvojena "uvoz fakture završen" kod-puta — dokumentovano
eksplicitno u CONTEXT.md §31 kao upozorenje za buduće agente da provjere SVA tri prije nego
zaključe da je slična izmjena kompletna.

## Konflikti / kontradiktorni izvori

Nema — ovo je DOPUNA (ne korekcija) prethodna dva fixa istog dana; sva tri izvještaja
(§29 supplier filter, §30 agent_mode uslov, §31 treći kod-put) zajedno čine kompletno
rješenje istog korisničkog zahtjeva.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | fix(agent): pokreni tarifnu provjeru i nakon agent uvoza (Uvezi u deklaraciju) |

## Rizici / ograničenja

- Nisam pronašao ČETVRTI kod-put, ali s obzirom na veličinu i istoriju ovog fajla (5100+
  linija u faktura_view.py, više paralelnih agent-related servisa), ne mogu garantovati da
  ne postoji još neki rijetko korišten import put (npr. drag-drop specifična grana, ili
  neki stariji/deprecated kod-put) koji i dalje zaobilazi sva tri sad pokrivena mjesta.

## Potreban follow-up

- Ručni test: agent uvoz kroz "Uvezi u deklaraciju" rutu treba sad automatski pokazati
  dijalog (ili tihu poruku "nema prijedloga" ako je selekcija-scoping relevantan — nije, ovo
  je uvijek uvoz cijele fakture, ne selekcija).
- Rebuild `.exe`-a za sledeći test ciklus.
- Ako se opet pojavi "ništa se nije desilo automatski" nakon NEKOG DRUGOG tipa uvoza,
  provjeriti da li postoji četvrti kod-put prije daljeg debugovanja postojeća tri.

## Potrebna korisnička potvrda

- Da li se dijalog sad pojavljuje automatski nakon uvoza kroz agent mod (istu rutu koju je
  korisnik ranije testirao).
