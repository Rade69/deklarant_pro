# Agent origin context fix — 2026-05-23

## Problem

Agent nije ispravno koristio kontekst prethodno pregledane stavke u Faktura tabu.
Nakon upita:

- `pogledaj stavku 53 u tabu faktura`
- `Potraži u bazi znanja zemlju porijkla za zaj proizvod`

agent je odgovorio opštim spiskom ISO zemalja umjesto da pretraži istoriju za proizvod
`DEPIWHITE ADV.KREM 40 ml`.

## Uzrok

Routing za porijeklo je bio preuzak:

- nije prepoznavao tipfelere poput `porijkla` i `prijekla`,
- nije koristio `last_invoice_line_ordinal` / `last_product_name` za upite tipa `taj/zaj proizvod`,
- upit je zbog toga padao u generički AI odgovor umjesto lokalnog alata za porijeklo.

## Implementacija

Izmijenjen je `gui/tabs/agent/services/chat_intent_handler.py`:

- dodat zajednički regex za porijeklo sa tolerantnim oblicima:
  `porijek*`, `porijk*`, `porekl*`, `prijek*`, `zemlja por*`,
- dodat `_origin_lookup_from_context()` koji koristi zadnju pregledanu faktura-stavku,
- `_resolve_contextual_request()` sada prvo hvata kontekstualne upite za porijeklo prije generičke baze,
- ekstrakcija proizvoda ignoriše slabe fragmente poput `u bazi znanja zemlju` i `u ranijim deklaracijama`.

## Testovi

Dodati regresioni testovi u `tests/unit/test_chat_context_followups.py`:

- upit sa tipfelerom `porijkla` i `zaj proizvod` koristi zadnju faktura-stavku,
- upit `DEPIWHITE ADV.KREM 40 ml kojeg je prijekla...` izvlači pravi naziv proizvoda.

Pokrenuto:

```bash
python -m pytest tests/unit/test_chat_context_followups.py tests/unit/test_kg_fashion_manifest.py tests/unit/test_eur1_quick_dialog.py tests/unit/test_agent_processing_worker_sort.py -q
```

Rezultat: `35 passed`.

## Napomena

U radnom stablu su ostale nepovezane izmjene u `AGENTS.md`, `CLAUDE.md` i debug printovi u
`gui/tabs/faktura_view.py`. Nisu dio ovog commita.
