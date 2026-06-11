# Faza 4 - Tool-first agent router

## Kontekst

Faza 4 iz plana `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md` trazi da agent prvo koristi lokalne servise/alate, a LLM tek kao fallback za formulaciju ili nejasne upite.

Postojeci `ToolDispatcherWorker._dispatch()` je prvo pozivao DeepSeek tool-use. Ako DeepSeek nije bio podesen, lokalne akcije koje su vec mapirane u `_execute_tool()` nisu mogle proci kroz dispatcher.

## Sta je promijenjeno

- `services/agent/chat/tool_dispatcher.py`
- `dist_client/services/agent/chat/tool_dispatcher.py`
- `gui/tabs/agent/widgets/chat_worker.py`
- `dist_client/gui/tabs/agent/widgets/chat_worker.py`
- `tests/unit/test_tool_dispatcher.py`
- `agent_tasks/2026-06-11_faza4-handoff.md`

## Kako

Dodan je `route_local_tool(message)` u tool dispatcher.

`ToolDispatcherWorker._dispatch()` sada prvo pozove lokalni router:

1. Ako router prepozna sigurnu namjeru, vraca `DispatchResult(tool_call=...)`.
2. Postojeci signal `tool_call_received` ostaje isti.
3. Postojeci `_execute_tool()` u `chat_intent_handler.py` izvrsava isti alat kao i ranije.
4. Ako router ne prepozna namjeru, stari DeepSeek tool-use tok ostaje fallback.

Router pokriva samo visoko sigurne namjere:

- pregled stanja aplikacije
- provjeru tarifa
- pojedinacnu pretragu tarife
- batch prijedlog tarifa
- pretragu porijekla
- analizu tarifa po istoriji
- pretragu slicnih proizvoda

U `ChatWorker._system_prompt()` uklonjena je instrukcija da LLM daje tarifni broj iz opsteg znanja. Dodato je pravilo da za tarife, porijeklo, povlastice i validaciju koristi samo kontekst/lokalni izvor, a za `unknown` mora reci da nema dovoljno potvrdjenih podataka.

## Zasto

Ovo smanjuje zavisnost od LLM providera i rjesava dio problema gdje agent padne na API kljucu ili 402/429 gresci i ne uradi lokalno dostupnu akciju.

Promjena je namjerno ogranicena: ne mijenja poslovne servise, ne mijenja `_execute_tool()` mapiranje i ne uvodi novi eksterni servis.

## GitNexus

Impact prije izmjene:

- `ToolDispatcherWorker._dispatch` root: LOW
- `ToolDispatcherWorker._dispatch` dist_client: LOW
- `ChatWorker._system_prompt` root: LOW
- `ChatWorker._system_prompt` dist_client: LOW

## Provjere

Pokrenuto:

```powershell
python -m pytest tests/unit/test_tool_dispatcher.py -v
```

Rezultat:

```text
11 passed
```

Pokrenuto:

```powershell
python -m py_compile services\agent\chat\tool_dispatcher.py dist_client\services\agent\chat\tool_dispatcher.py gui\tabs\agent\widgets\chat_worker.py dist_client\gui\tabs\agent\widgets\chat_worker.py tests\unit\test_tool_dispatcher.py
```

Rezultat: bez greske.

