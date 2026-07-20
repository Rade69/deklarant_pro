# Faza D — standardizovani rezultati i audit (retrospektivan project_room)

## Cilj
Implementirati plan §8: `ToolResult` ugovor uključuje uspješne rezultate (efekat,
potvrda, operation_id), strukturisan audit svih routing slojeva (contextual/local/
tool_use/regex_fallback/plain_chat/pipeline), i konverzija aktivnih `print()` poziva
u runtime agent toku u logger.

## Pogođeno (`gitnexus_detect_changes` nakon svih izmjena)

`risk_level: critical`, 141 promijenjenih simbola, 21 fajl (root+dist_client parovi),
36 "affected_processes" (uglavnom `Run → X` execution flow trace-ovi).

**Napomena napisana NAKON izmjena** (izmjene su već urađene prije provjere — plan
§Faza D je unaprijed odobren od korisnika kao nastavak niza Faza A-C; ovaj fajl
dokumentuje analizu rizika prije commit-ovanja, ne prije editovanja).

## Analiza — zašto CRITICAL, i da li je zaslužen

Podijelio sam 21 fajl u dvije kategorije:

### Kategorija 1 — čisto kozmetički (print → logger), 5 fajlova
`services/agent/llm_audit_log.py`, `services/agent/tariff/tariff_rag_service.py`,
`services/agent/tariff/tariff_suggestion_service.py`, `gui/tabs/agent/agent_controller.py`,
`gui/tabs/agent/widgets/chat_worker.py` (+ dist_client parovi = 10 fajlova).

Provjerio sam `git diff` liniju po liniju za sve — SVAKA izmjena je zamjena
`print(...)` → `logger.warning/debug/error(...)` unutar `except` blokova ili jedne
debug cache-clear poruke. Nijedna ne dira `return` vrijednost, argument, kontrolni
tok, ili emit-ovan Qt signal. GitNexus ih označava "touched" jer se nalaze unutar
funkcija visokog fan-in-a (`ChatWorker.run`, `_pg_today_stats`,
`_get_basic_suggestions`) koje učestvuju u desetinama execution-flow trace-ova —
to je razlog za veliki broj "affected_processes", ne stvaran bihevioralni rizik.

### Kategorija 2 — stvarna funkcionalna proširenja, 4 fajla (+ audit_log.py novi)
`services/agent/chat/tool_result.py`, `services/agent/chat/tool_dispatcher.py`,
`gui/tabs/agent/services/chat_intent_handler.py`,
`gui/tabs/agent/services/import_pipeline_service.py` (+ dist_client parovi).

Jedina promjena koja mijenja **oblik** postojećeg ugovora: `ToolDispatcherWorker`
signali `tool_call_received`/`fallback_to_chat` dobili treći/drugi parametar
(`provider`). Provjereno `grep`-om kroz CIO repo (root+dist_client, uklj. testove):
**jedino mjesto** koje se povezuje na ova dva signala je
`gui/tabs/agent/services/chat_intent_handler.py:_handle_message` — već ažurirano
da prima novi parametar. Nema drugih pozivalaca, nema testova koji direktno
povezuju te signale.

Ostale izmjene u ovoj kategoriji su aditivne (nova polja sa default vrijednostima
na `ToolResult`, novi `operation_id` guard koji SAMO dodaje early-return granu za
već obrađen slučaj, novi audit pozivi koji ne mijenjaju postojeći tok).

## Verifikacija (dokaz da je bezbjedno)

```
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
→ 803 passed, 58 skipped, 4 failed (sve 4 pretpostojeće/okolinske, nepovezane —
  vidi agent_report), 1 error (test_model_benchmark.py, pretpostojeći fixture gap)

python -m py_compile <svih 10 izmijenjenih + 1 novi fajl, root i dist_client> → OK

diff (bez BOM) root/dist_client za svih 10 fajlova → IDENTIČNI

grep za tool_call_received/fallback_to_chat .connect/.emit u cijelom repou
→ tačno 2 mjesta (emit u tool_dispatcher.py, connect u chat_intent_handler.py),
  oba ažurirana konzistentno
```

## Zaključak

CRITICAL oznaka je artefakt obima (9 produkcijskih fajlova u jednom prolazu,
tačno kako plan §8 i predviđa za "standardizuj rezultate i audit dogadjaje") i
GitNexus-ovog brojanja kroz visoko-centralne funkcije, ne dokaz krhke/rizične
izmjene. Jedina promjena oblika postojećeg ugovora (Qt signal signatura) je
provjerena i ima tačno jednog pozivaoca, već usklađenog. Nastavljam sa
commit-ovanjem — korisnik je unaprijed odobrio Fazu D kao cjelinu.

## Šta NE dirati (potvrđeno nepromijenjeno)
- `gui/tabs/faktura_view.py`, `gui/tabs/naimenovanja_view.py` — netaknuti
- `services/decision/*` — netaknuto
- Interna poslovna logika tarifnog/porijeklo matchinga — netaknuta (samo
  except-blok diagnostika)
