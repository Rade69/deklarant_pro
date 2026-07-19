# Faza B — LLM provider unifikacija (HIGH impact plan)

## Cilj
Ukloniti direktan DeepSeek API poziv iz `tool_dispatcher.py` (van `LLMProvider`
apstrakcije) i, po eksplicitnoj korisničkoj potvrdi, ukloniti OpenRouter/DeepSeek
iz `LLMProvider`-ovog fallback lanca u potpunosti (samo Groq → Gemini ostaje,
usklađeno sa AGENTS.md).

## Pogođeno (gitnexus_impact)

- `LLMProvider` (klasa): **HIGH**, 34 impacted, 16 direktnih uvoznika —
  centralna klasa, koriste je `tool_dispatcher.py`, `intent_classifier.py`,
  `tariff_intent_service.py`, `chat_worker.py`, `chat_intent_handler.py`
  (`_AltTariffWorker`, `_ClassifierWorker`), `system_panel.py`, `tariff_llm_worker.py`
  (root + dist_client za svaki).
- `has_deepseek()`: **HIGH**, 19 impacted, 2 pogođena procesa
  (`chat_worker.py:run`, `tariff_llm_worker.py:run`) — **otkriven stvaran rizik**:
  `SystemPanel._on_ai_health_clicked` (admin panel, AI health check dijagnostika)
  direktno poziva `has_deepseek()`, `has_openrouter()`, `deepseek_key`,
  `openrouter_key` — brisanje bez ažuriranja ovog panela bi izazvalo
  `AttributeError` pri kliku na "AI Health Check" dugme.

## Plan

1. `gui/tabs/agent/widgets/llm_provider.py` — ukloniti DeepSeek/OpenRouter
   (atribute, metode, grane u `stream_chat`/`complete`/`active_provider`),
   dodati `complete_with_tools()` + `ProviderToolResponse` (Groq + Gemini).
2. `gui/tabs/admin/panels/system_panel.py::_on_ai_health_clicked` — ukloniti
   DeepSeek/OpenRouter redove iz health check-a (jedini pogođen vanjski pozivalac).
3. `services/agent/chat/tool_dispatcher.py` — zamijeniti direktan
   `OpenAI(base_url=deepseek)` poziv sa `LLMProvider.complete_with_tools()`.
4. `services/agent/chat/intent_classifier.py` — samo zastarjeli komentari
   (već koristi `LLMProvider.complete()` ispravno), nema koda za mijenjati.
5. `docs/decisions/001-tool-use-refactoring.md`, `002-tool-dispatcher-integration.md`
   — ažurirati opis provider toka (DeepSeek → Groq/Gemini kroz LLMProvider).

## Šta NE dirati

- `gui/tabs/admin/panels/analytics_panel.py:252` — `boje['deepseek']` je
  neaktivan dict entry u color-lookup mapi (nikad se neće matchovati nakon
  izmjene), potpuno bezopasno ostaviti — nije funkcionalni bug.
- Faza A kod (`tool_policy.py`, mutation gate) — netaknuto, samo se koristi
  (`is_known_tool` validacija tool imena vraćenog od providera).
- Regex fallback sloj u `chat_intent_handler.py` — ostaje (plan §10.2, ne
  briše se dok telemetrija ne potvrdi da nije potreban).

## Konflikti
Nema. Korisnik je eksplicitno potvrdio "Ukloni oba iz lanca" prije početka
ovog zahvata (vidi razgovor).

## Nivo dozvole
`fix + refactor`, mandatory review (korisnik pregleda nakon Faze B, kao i
nakon Faze A).
