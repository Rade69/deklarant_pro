# 002 — ToolDispatcher integracija u ChatIntentHandler

**Datum:** 2026-04-29
**Status:** U implementaciji
**Zavisi od:** 001-tool-use-refactoring.md

## Izmjena

Dodaje se ToolDispatcherWorker kao **prvi sloj** chat routing-a u `_handle_message()`.

Novi flow:
```
poruka
  → injection check
  → pending action check
  → ToolDispatcherWorker (DeepSeek tool use)
      → tool_call → _execute_tool() → servis → DONE
      → fallback_to_chat → ChatWorker (plain LLM)
      → error → stari regex sloj (fallback)
```

## Zašto zadržavamo regex sloj

Regex sloj ostaje kao **fallback** za slučaj:
- DeepSeek API nije dostupan (nema ključa, rate limit)
- Mrežna greška
- Bilo koji drugi izuzetak

Kad Tool Use bude stabilan u produkciji 2-3 nedjelje, regex sloj se briše (Faza 3).

## `_execute_tool()` mapiranje

Mapira tool call-ove na postojeće servisne metode:

| Tool | Metod | Parametri |
|------|-------|-----------|
| `predlozi_tarife` | `ctrl._predlozi_tarifne_brojeve()` ili `tariff_svc.propose_by_filter(filter)` | `filter: str?` |
| `provjeri_tarife` | `ctrl._provjeri_tarifne_za_naziv()` ili kroz IntentClassifier | — |
| `pretrazi_tarifu` | `_pretrazi_tarifu(ctrl, args['naziv'])` | `naziv: str` |
| `validuj_deklaraciju` | `_compliance_check(ctrl)` | — |
| `prikazi_naimenovanja` | `_pregledaj_naimenovanja(ctrl)` | — |
| `upisi_u_kolonu` | `naim_intent_svc._resolve_kolona()` + `execute()` | `kolona, vrijednost, tab` |
| `spoji_naimenovanja` | `ctrl._predlozi_spajanje_naimenovanja()` | — |

## Međuzavisnosti

- `tool_dispatcher.py` → zavisi od `tool_definitions.py`, `llm_provider.py`
- `chat_intent_handler.py` → zavisi od `tool_dispatcher.py`, postojećih servisa
- Kontroler (`agent_controller.py`) → ne mijenja se (samo dodajemo pozive kroz postojeće interfejse)
