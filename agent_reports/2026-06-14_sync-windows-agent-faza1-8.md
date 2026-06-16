# Sync: Faza 1-8 agent unapređenja iz `windows` grane u `dev`

**Datum:** 2026-06-14
**Grana:** `sync/windows-agent-faza1-8` (bazirana na `dev`)

## Šta je urađeno

Preneseni su funkcionalni (ne-Windows-rendering) dijelovi Faza 1-8 iz plana
`agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`, koji su
postojali samo u zastarjeloj `windows` grani:

1. **Evidence model** (`services/agent/validation/evidence_model.py`) — model
   pouzdanosti odluka agenta (score, confidence, requires_confirmation,
   auto_applicable) sa helperima za prikaz badge-ova.
2. **ToolResult struktura** (`services/agent/chat/tool_result.py`) —
   standardizovani odgovori alata (needs_review/unknown/error) + render u HTML.
3. **Lokalni tool router** (`route_local_tool` u `tool_dispatcher.py`) —
   regex prepoznavanje čestih upita prije LLM poziva.
4. **Sistem prompt pravilo** — agent ne smije izmišljati tarife/porijeklo/
   povlastice bez lokalnog izvora (`TOOL_RESULT_PROMPT_RULE`).
5. **402 Insufficient Balance fallback** u `llm_provider.py`.
6. **Faza 2 pravilo: povlastica zahtijeva PE1/PE2/PE3 dokaz** — primijenjeno
   u 6 fajlova (faktura_view, preflight dijalog, declaration_validator,
   auto_fill_service, product_master_list, tariff_mapping_service).
7. **Badge prikaz pouzdanosti** za tarifne prijedloge (chat + validation dialog).
8. **Strukturirani ToolResult odgovori** u `chat_intent_handler.py` za sve
   "nedostaje argument" / "nepoznata akcija" grane.
9. **"Copy report" dugme** u chat panelu (kopira posljednju poruku agenta).
10. **historical_tariff_search_service** — vraćen na per-liniju pretragu +
    dodano `Evidence` polje na `TariffHistoryMatch`.
11. **agent_controller fixevi** — natural sort (int/str tuple TypeError),
    `consumed_paths`-bazirani dedup uvoznih fajlova, auto-popuna zaglavlja
    pri manuelnom uvozu po fajlu.

## Kako je urađeno

- Diff `git diff origin/dev origin/windows -- <fajl>` za svaki fajl iz Faza 1-8.
- Nove fajlove i testove kopirani verbatim (`git show origin/windows:<path> > <path>`).
- Za postojeće fajlove, diff primijenjen selektivno (cherry-pick), uz
  prilagođavanje gdje se dev otad razvio dalje (vidi "Zašto / odluke" ispod).
- Iterativno pokretani testovi (`tests/unit/test_tool_dispatcher.py`,
  `test_chat_panel.py`, `test_llm_provider_fallback.py`,
  `test_auto_handle_povlastice_agent.py`, `test_preflight_preference_evidence.py`,
  `test_tariff_intent_service.py`, `test_agent_decision_regression.py`,
  `test_historical_tariff_validation.py`, `test_tariff_validation_dialog.py`)
  do zelenog stanja.
- Finalna provjera: `pytest tests/unit` → 550 passed, 2 failed (pre-existing,
  nevezano — `test_declaration_search_service.py`, potvrđeno `git stash`
  poređenjem sa `origin/dev`).
- Import sanity check: `QT_QPA_PLATFORM=offscreen python -c "import ..."` za
  svih 15 izmijenjenih modula — bez circular-import problema.

## Zašto (odluke i alternative)

- **`tariff_mapping_service.py`** — windows diff (134 linija) je mješavina
  uklanjanja `povlastica` auto-postavljanja (ŽELJENO) i reverzije dev-ovih
  kasnijih batch/performance optimizacija + promjene similarity threshold
  0.95→0.98 (NEŽELJENO, regresija). Cherry-pickovan samo prvi dio.
- **`agent_controller.py`** — windows diff je uklanjao
  `HistoricalLearningServiceSafe.preload_top_exporters()`. Ostavljeno kako
  jeste — dev-only performance feature, nevezano za Faza 1-8.
- **`historical_tariff_search_service.py`** — dev je imao batch-cache
  refactor (`cur=`, `_cache`, jedna konekcija) koji nije odgovarao novim
  testovima (preneseni iz windows, 24 testa). Vraćen na per-liniju
  `_search_one()` bez `cur=`, dodato `evidence` polje — genuina
  funkcionalna nadogradnja (Evidence sada teče u `TariffHistoryMatch`).
- **Faza 2 povlastica pravilo** — poslovni razlog: zemlja porijekla sama nije
  dovoljan dokaz za preferencijalni tretman (Rub.36); potreban je PE1
  (EUR.1 broj), PE2 (izjava o porijeklu) ili PE3 (izjava ovlašćenog
  izvoznika). Ranija logika je tiho postavljala `povlastica` iz master
  liste/baze mapiranja samo na osnovu zemlje, što je bilo netačno.

## Commitovi

| Hash | Poruka |
|------|--------|
| 9791808 | feat(agent): dodaj Evidence model i ToolResult strukturu |
| 977b972 | feat(agent): lokalni tool router, ToolResult pravilo u promptu i 402 fallback |
| 595dfc9 | fix(povlastice): povlastica se ne postavlja bez PE1/PE2/PE3 dokaza |
| f50dd65 | feat(agent-ui): prikaz pouzdanosti (badge) za tarifne prijedloge |
| c36f022 | feat(agent): strukturirani ToolResult odgovori za nedostajuće argumente |
| 693d81b | feat(agent-ui): dugme za kopiranje posljednje poruke agenta |
| 6dd9d35 | fix(agent): vrati historical_tariff_search_service na per-liniju pretragu + Evidence |
| 1d158b2 | fix(agent-controller): natural sort, consumed_paths dedup i auto-popuna zaglavlja |

## Testovi

- `tests/unit` ukupno: 550 passed, 2 failed (pre-existing, nevezano).
- Pre-existing failures: `test_declaration_search_service.py::test_declaration_search_uses_env_paths`,
  `::test_declaration_search_requires_meaningful_token_overlap` — padaju i na
  čistom `origin/dev` (commit `31e7195`), izvan opsega ovog zadatka.

## Sljedeći korak

Grana `sync/windows-agent-faza1-8` je spremna za merge/PR u `dev` nakon review-a.
