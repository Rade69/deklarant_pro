# 001 — Tool Use refaktoring chat routing sloja

**Datum:** 2026-04-29
**Status:** U implementaciji

## Problem

Trenutni chat routing u Deklarant Pro koristi 3 sloja:

```
poruka → 80+ keyword regex-a → IntentClassifier (LLM) → ChatWorker (LLM)
```

Rezultat: sporo (1-3 LLM poziva), krhko (regex ne pokriva varijacije jezika), teško za
održavanje (300+ linija regex koda u `chat_intent_handler.py`).

## Odluka

Zamijeniti 3-slojni routing sa **Tool Use** pristupom:

```
poruka → LLMProvider.complete_with_tools() (Groq → Gemini, tools=[...]) → tool_call → executor → rezultat
```

> **Ažurirano 2026-07-19 (Faza B, docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md):**
> Provider je bio DeepSeek (direktan `OpenAI(base_url="https://api.deepseek.com")`
> poziv u `tool_dispatcher.py`, mimo `LLMProvider` apstrakcije). Zamijenjeno sa
> `LLMProvider.complete_with_tools()` — isti Groq → Gemini lanac kao standardni
> chat, bez direktnog kreiranja provider klijenta van `LLMProvider`.
> OpenRouter/DeepSeek su u istoj fazi uklonjeni i iz `LLMProvider`-ovog
> fallback lanca u potpunosti (kanonska politika: `AGENTS.md`).

Zašto:
- **1 LLM poziv** umjesto 1-3 — brže i jeftinije
- **Nema regex-a** — model razumije prirodni jezik ("jesu li tarife ok?" = "provjeri tarife")
- **Automatska proširivost** — novi alat ne zahtijeva novi regex
- **Brisanje 300+ linija** mrtvog koda

## Alati (inicijalni set)

| Alat | Servis | Parametri |
|------|--------|-----------|
| `predlozi_tarife` | TariffIntentService | `filter: string?` |
| `provjeri_tarife` | TariffIntentService | — |
| `pretrazi_tarifu` | TarifaService | `naziv: string` |
| `validuj_deklaraciju` | ComplianceCheckService | — |
| `prikazi_naimenovanja` | NaimenovanjaReviewService | — |
| `upisi_u_kolonu` | NaimenovanjaIntentService | `kolona, vrijednost, tab` |
| `spoji_naimenovanja` | MergeIntentService | — |

## Rizici i mitigacije

| Rizik | Mitigacija |
|-------|-----------|
| Model halucinira tarifne brojeve umjesto da pozove alat | Agresivni system prompt: "NIKAD ne izmišljaj tarifne brojeve" |
| Model ne poziva alat za očigledne slučajeve | `tool_choice: "auto"` uz jake opise alata |
| Merge zahtijeva potvrdu (multi-turn) | Tool vraća `requires_confirmation`, dispatcher setuje `_pending_action` |
| Groq/Gemini imaju različit tool-call format | `LLMProvider.complete_with_tools()` normalizuje oba u neutralan `ProviderToolResponse` prije nego stigne do dispatchera |

## Povezani fajlovi

- `chat_intent_handler.py` — glavni fajl za refaktoring
- `intent_classifier.py` — za brisanje (zamijenjen tool use)
- `llm_provider.py` — dodati `tools` parametar
- `tests/test_tool_use.py` — evaluacioni testovi

## Međuzavisnosti

- **NaimenovanjaIntentService** — koristi se za `upisi_u_kolonu`
- **TariffIntentService** — koristi se za `predlozi_tarife`, `provjeri_tarife`
- **MergeIntentService** — koristi se za `spoji_naimenovanja`
- **ComplianceCheckService** — koristi se za `validuj_deklaraciju`
- **NaimenovanjaReviewService** — koristi se za `prikazi_naimenovanja`
- **TarifaService** — koristi se za `pretrazi_tarifu`
- **ChatWorker** — ostaje za plain chat kad nema tool call-a
