# Agent report - Faza 4: tool-first agent

**Datum:** 2026-06-11
**Agent:** Codex
**Scope:** Tool dispatcher/chat handler, ChatWorker prompt guard, strukturisani tool rezultat

## Sta je uradjeno

- Dodan je zajednicki `ToolResult` model sa statusima `ok`, `needs_review`, `unknown` i `error`.
- Dodan je HTML renderer koji svaki strukturisani rezultat prikazuje sa izvorom i statusom.
- `ChatIntentHandler._execute_tool()` sada za nedostajuce argumente, neprepoznatu kolonu i nepoznat tool koristi `ToolResult`, umjesto slobodnog upozoravajuceg teksta bez izvora.
- `ChatWorker` system prompt sada eksplicitno zabranjuje LLM-u da mijenja znacenje strukturisanog `TOOL_RESULT` odgovora.
- Isto je preslikano u `dist_client` mirror.

## Zasto je donesena odluka

Faza 4 ne trazi da LLM postane pametniji, nego da bude disciplinovaniji. Agent prvo mora pokusati lokalni tool ili servis, a ako servis vrati `unknown` ili `needs_review`, taj status mora ostati netaknut. LLM smije samo uljepsati ili formatirati rezultat, ali ne smije dodati tarifu, porijeklo, povlasticu ili zakljucak koji tool nije dao.

## Sta nije mijenjano

- Nisu mijenjani parseri, XML export ni baza.
- Nije mijenjana logika stvarnog popunjavanja tarifa, spajanja naimenovanja ili validacije.
- Postojeci deterministicki GUI odgovori ostaju direktni; novi sloj pokriva granicne `unknown`/`needs_review` situacije i prompt guard.

## Verifikacija

- `python -m py_compile` nad izmijenjenim Python fajlovima.
- `python -m pytest tests\unit\test_tool_result.py tests\unit\test_tool_dispatcher.py -q`
