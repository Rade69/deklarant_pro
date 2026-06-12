# Agent report — Faza 8: LLM provider fallback (402/429/timeout)

**Datum:** 2026-06-12
**Agent:** Claude Sonnet 4.6
**Scope:** `gui/tabs/agent/widgets/llm_provider.py` (+ `dist_client` mirror),
`tests/unit/test_llm_provider_fallback.py` (novo),
`agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`

## Sta je uradjeno

- `parse_llm_error()` u `gui/tabs/agent/widgets/llm_provider.py` (i identicna
  kopija u `dist_client/`) dobio novu granu za HTTP 402 / "Insufficient
  Balance", smjestenu izmedju postojecih 401 i timeout/connection grana:
  ```python
  if '402' in msg or 'insufficient_balance' in msg.lower() or 'insufficient balance' in msg.lower():
      return (
          "💳 Nedovoljno kredita na AI nalogu (402 Insufficient Balance).\n"
          "Dopuni kredit za trenutni provider ili podesi drugi (GROQ_API_KEY, GEMINI_API_KEY "
          "ili OPENROUTER_API_KEY) u .env."
      )
  ```
- Novi `tests/unit/test_llm_provider_fallback.py` (10 testova):
  - `parse_llm_error` — 402 (novo), 429 (sa i bez Used/Limit), 401, timeout,
    generic fallback (regresija postojecih grana).
  - `LLMProvider.stream_chat()` / `.complete()` — bounded fallback chain
    (Groq → Gemini → OpenRouter → DeepSeek), svaki provider tacno jednom pa
    propagira posljednju gresku; i slucaj kad nijedan provider nije podesen
    (`RuntimeError("Nema dostupnog AI providera...")`).
  - `ToolDispatcherWorker._dispatch()` — kad DeepSeek API vrati 402, dispatcher
    vraca `DispatchResult(error=...)` sa prevedenom porukom (bez "Traceback"),
    umjesto da propagira izuzetak.
- `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md` — Faza 8
  status postavljen na "ZAVRSENO 2026-06-12", dodan "Uradjeno" odjeljak.

## Kako je uradjeno

Izmjena u `parse_llm_error()` je cisto additivna — nova `if` grana ubacena
izmedju postojecih 401 i timeout provjera, bez izmjene signature ili
postojecih grana. `_is_rate_limit(exc)` (linija 37-38) je potvrdjena dead code
(grep, nigdje pozvana) — netaknuta.

Za testove je koristen monkeypatch direktno na metode `LLMProvider` klase
(`has_groq`/`has_gemini`/`has_openrouter`/`has_deepseek`,
`_groq_stream`/`_gemini_stream`/`_openrouter_stream`/`_deepseek_stream`,
`_*_complete`), umjesto mockovanja `groq`/`openai`/`google.genai` SDK
klijenata direktno — jednostavnije i nema potrebe za API kljucevima.

Za `ToolDispatcherWorker._dispatch()` test, `openai.OpenAI` je monkeypatch-ovan
na fake klasu cija `chat.completions.create()` baca 402 izuzetak (DeepSeek
format greske). Patch radi jer `_dispatch()` koristi `from openai import
OpenAI` unutar funkcije — `from X import Y` se rezolvira na `X.Y` u trenutku
poziva, pa patch na `openai.OpenAI` hvata i lokalni import.

Poruka koja se salje u dispatcher (`"dobar dan, kako si"`) je odabrana jer
NE pogadja `route_local_tool()` (vidi postojeci `test_tool_dispatcher.py`),
sto osigurava da test stvarno testira put kroz DeepSeek poziv.

## Zasto ovako (analiza postojece arhitekture, bez izmjene koda)

Plan Faze 8 trazi i: "Ako LLM padne, koristiti lokalni tool rezultat ako
postoji" i "Ne pokusavati beskonacne retry petlje". Analiza je pokazala da su
OBA pravila VEC implementirana prije ove faze:

1. **Lokalni tool prvo** — `route_local_tool()` u
   `services/agent/chat/tool_dispatcher.py` se poziva PRIJE bilo kakvog LLM
   poziva u `ToolDispatcherWorker._dispatch()`. Dodatno, `_on_error` u
   `gui/tabs/agent/services/chat_intent_handler.py` rutira 402/429/timeout
   greske na `_handle_message_regex_fallback` (lokalni DB-bazirani tool-ovi)
   umjesto direktno na `ChatWorker`, OSIM ako greska indicira da DeepSeek
   kljuc nije podesen/neispravan (provjera substring "deepseek" + "kljuc").
   Postojeci `test_dispatch_uses_local_router_before_llm` ovo vec pokriva.
2. **Bez beskonacnih retry petlji** — `stream_chat()`/`complete()` u
   `LLMProvider` su try/except lanac koji pokusava Groq → Gemini →
   OpenRouter → DeepSeek TACNO JEDNOM svaki, bez `while`/retry logike. Novi
   testovi ovo zakljucavaju kao regresiju.

Zato kodna izmjena za Fazu 8 je SAMO 402 grana — ostatak acceptance kriterija
je pokriven novim regresionim testovima nad postojecom arhitekturom (isti
pristup kao Faza 7: "testovi kao regresija za postojeca + nova pravila").

## GitNexus

- `gitnexus_impact(target="parse_llm_error", direction="upstream")` → risk
  **HIGH** (9 impacted symbols, 7 direktnih pozivaca: `ChatWorker.run`,
  `TariffLLMWorker.run`, `_AltTariffWorker.run` x2 (root+dist_client),
  `ToolDispatcherWorker._dispatch`/`run` x2, `_parse_groq_error`; 2 affected
  processes, 3 affected modules). Rizik prijavljen korisniku per CLAUDE.md;
  nastavljeno jer je izmjena cisto additivna (nova rano-return grana, bez
  promjene signature/ponasanja postojecih grana za druge tipove gresaka).
- `gitnexus_detect_changes(scope=all)` → risk **LOW**, 0 affected processes.
  Promijenjeni simboli: `parse_llm_error`/`LLMProvider` (root + dist_client),
  plan sekcije (Faza 8), i auto-generisani GitNexus brojaci u
  `AGENTS.md`/`CLAUDE.md`. Novi test fajl je cisto dodatni.
- `npx gitnexus analyze` pokrenut nakon commitova (38927→38955→38984 nodes,
  61157→61206→61259 edges) — drift commitovan kao prateci `chore`.

## Testovi

```powershell
python -m py_compile tests/unit/test_llm_provider_fallback.py
python -m py_compile dist_client/gui/tabs/agent/widgets/llm_provider.py gui/tabs/agent/widgets/llm_provider.py
python -m pytest tests/unit/test_llm_provider_fallback.py -v
python -m pytest tests/unit -k "agent or evidence or tariff or llm" -q
```

Rezultat: `10 passed` za novi fajl; širi set `165 passed, 10 failed, 1
skipped` — 10 padova su pre-existing `FileNotFoundError` za `najavauvoza/`
fixture fajlove, nepovezano sa ovom izmjenom (ista baseline kao u Fazi 6/7).

## Commitovi

| Hash | Poruka |
| --- | --- |
| `5a99ad1` | `chore(gitnexus): azuriraj broj simbola/relacija u AGENTS.md i CLAUDE.md` (pred-Faza 8 drift) |
| `91bb364` | `feat(agent): civilizovan LLM fallback za 402/429/timeout greske (Faza 8)` |
| `4cf797e` | `chore(gitnexus): azuriraj broj simbola/relacija nakon Faze 8` |

## Otvoreno za naredne faze

- Faza 8 je posljednja faza navedena u
  `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`
  ("Redoslijed delegiranja" lista Agente A-E za Faze 1-8) — sve faze 1-8 su
  sada ZAVRSENE.
- Ako se zeli dodatno testirati UI wiring (`error_occurred.connect(...)` →
  `chat.add_agent_message(f"⚠️ {err}")`), to bi bio Qt-signal integracioni
  test u `tests/unit/test_chat_worker.py` stilu — van scope-a ove faze jer
  acceptance kriterij "UI poruka je razumljiva korisniku" je vec zadovoljen
  postojecim wiring-om + novom 402 porukom.
