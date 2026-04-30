# Agent origin query routing

Datum: 2026-04-30

## Problem
Korisnik može pitati agent tab: `KONDENZATOR GCVC RD 045.2/24-53, potraži porijeklo ovog proizvoda`.
Tool Use routing je ranije imao alat za pretragu tarife, ali nije imao alat za porijeklo proizvoda.
Zato je model često birao najbliži postojeći alat (`pretrazi_tarifu`) i vraćao tarifne rezultate,
iako korisnik traži zemlju porijekla.

## Nova logika
Dodana su dva sloja zaštite:

1. Lokalni pre-filter u `chat_intent_handler.py` hvata upite o porijeklu prije DeepSeek Tool Use poziva.
2. Tool schema sada ima eksplicitan alat `pretrazi_porijeklo(naziv)` za slučajeve koji ipak idu kroz model.

`pretrazi_porijeklo` koristi `DeclarationSearchService.search_by_goods()` i vraća zemlje porijekla iz
lokalnog indeksa istorijskih XML deklaracija. Ako nema nalaza, agent jasno kaže da ne može pouzdano
utvrditi porijeklo i ne nudi tarifne brojeve.

## Implementacija
Fajlovi:
- `gui/tabs/agent/services/chat_intent_handler.py`
- `services/agent/chat/tool_definitions.py`

Ključne tačke:
- `_extract_origin_product_query(message)` izdvaja naziv proizvoda iz formulacija sa `porijeklo`,
  `poreklo`, `origin` i `zemlja porijekla`.
- Upis u kolonu (`upiši porijeklo TR`) ne smije biti presretnut kao pretraga porijekla.
- `_pretrazi_porijeklo(ctrl, upit)` formatira rezultate po zemlji porijekla i navodi izvor.

## Provjera
Targetirani test pokriva:
- proizvod prije zareza + zahtjev za porijeklo,
- proizvod nakon fraze `zemlja porijekla za`,
- zaštitu da se `upiši porijeklo` i dalje tretira kao upis u kolonu.

Test:
`python -m pytest tests/test_origin_intent_routing.py -q`
