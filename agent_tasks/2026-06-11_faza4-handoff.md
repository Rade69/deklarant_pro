# Faza 4 - Tool-first agent - handoff

## Cilj

Agent mora prvo pokusati deterministicki lokalni routing prema postojecim alatima, a LLM smije biti samo fallback za nejasne ili informativne poruke. Time se izbjegava situacija da agent ne moze uraditi osnovne lokalne akcije kada nema DeepSeek/Gemini/OpenRouter kljuca ili kada provider vrati 402/429/timeout.

## Scope

Primarni fajlovi:

- `services/agent/chat/tool_dispatcher.py`
- `dist_client/services/agent/chat/tool_dispatcher.py`
- `gui/tabs/agent/widgets/chat_worker.py`
- `dist_client/gui/tabs/agent/widgets/chat_worker.py`
- `tests/unit/test_tool_dispatcher.py`

Ne dirati u ovoj fazi bez posebne odluke:

- poslovne servise za tarife, porijeklo, validaciju i naimenovanja
- `gui/tabs/agent/services/chat_intent_handler.py::_execute_tool`
- LLM provider implementacije
- MCP facade fallback logiku

## Implementaciona odluka

Postojeci `ToolDispatcherWorker._dispatch()` je do sada prvo zvao DeepSeek tool-use. Faza 4 uvodi lokalni `route_local_tool(message)` koji se izvrsava prije LLM poziva.

Ako lokalni router prepozna namjeru, vraca `DispatchResult(tool_call=...)` i worker emituje postojece `tool_call_received`. Ako ne prepozna, stari LLM tool-use tok ostaje nepromijenjen.

To je namjerno mali rez:

- ne mijenja format signala
- ne mijenja `_execute_tool`
- ne mijenja poslovnu logiku
- kompatibilan je sa postojecim DeepSeek routingom

Drugi dio Faze 4 je prompt guard u `ChatWorker._system_prompt()`: LLM vise ne dobija instrukciju da daje tarifne brojeve iz opsteg znanja, nego mora koristiti kontekst/lokalni izvor ili jasno reci da nema dovoljno potvrdjenih podataka.

## Minimalni lokalni routing za Fazu 4

Lokalni router treba pokriti samo visoko sigurne namjere:

- `pregled_stanja_aplikacije`
  - "pogledaj tab faktura"
  - "sta je u zaglavlju"
  - "stanje aplikacije"
  - scope: `faktura`, `naimenovanja`, `zaglavlje`, `all`
- `provjeri_tarife`
  - "provjeri tarife"
  - "jesu li tarifni brojevi ispravni"
- `pretrazi_tarifu`
  - "koji je tarifni broj za X"
  - "predlozi tarifu za X"
- `predlozi_tarife`
  - "popuni sve tarife"
  - "predlozi tarife"
- `pretrazi_porijeklo`
  - "porijeklo proizvoda X"
  - "zemlja porijekla za X"
- `analiziraj_tarifne`
  - "analiziraj tarifne"
  - "uporedi tarifne sa istorijom"
- `pronadji_slicne_proizvode`
  - "slicni proizvodi za X"
  - "raniji slicni slucajevi za X"

Za sve ostalo `route_local_tool()` vraca `None` i prepusta poruku LLM fallbacku.

## Acceptance kriteriji

- Kad DeepSeek API kljuc nije podesen, lokalno prepoznate akcije i dalje vracaju `tool_call`.
- Za lokalno nepoznatu poruku bez DeepSeek kljuca ostaje postojeca greska/fallback.
- Chat odgovor i dalje ide preko postojecih servisa, pa izvor podataka ostaje na servisnom nivou.
- Testovi ne smiju koristiti vanjski LLM niti API kljuceve.

## Testovi

Dodati `tests/unit/test_tool_dispatcher.py`:

- lokalno routanje pregleda faktura/zaglavlja
- lokalno routanje provjere tarifa
- lokalno routanje pojedinacne pretrage tarife
- lokalno routanje batch prijedloga tarifa
- lokalno routanje porijekla
- unknown poruka vraca `None` iz local routera
- `_dispatch()` prvo koristi lokalni router i ne zahtijeva DeepSeek za prepoznatu akciju
- ChatWorker prompt sadrzi pravilo da se za unknown/nepoznato ne izmisljaju sifre, porijeklo ili povlastice

## GitNexus

Impact prije izmjene:

- `ToolDispatcherWorker._dispatch` root: LOW, direktno zavisi `ToolDispatcherWorker.run`
- `ToolDispatcherWorker._dispatch` dist_client: LOW, direktno zavisi `ToolDispatcherWorker.run`

## Provjera

Pokrenuti:

```powershell
python -m pytest tests/unit/test_tool_dispatcher.py -v
python -m py_compile services\agent\chat\tool_dispatcher.py dist_client\services\agent\chat\tool_dispatcher.py tests\unit\test_tool_dispatcher.py
```

Prije commita:

```text
gitnexus_detect_changes(scope="all")
```
