# Agent context and EUR1 hardening

Datum: 2026-05-22

## Sažetak

Implementiran je novi sloj konteksta za Carinskog Agenta i dovršene su dorade EUR.1 dijaloga po fakturi. Agent sada može čitati aktivni draft kroz centralni snapshot servis, razumjeti konkretne reference na tab Faktura i tab Naimenovanja, te izvesti akcije nad posljednje otvorenom fakturnom stavkom.

## Šta je urađeno

- Dodan `ApplicationContextService` za pregled stanja aplikacije:
  - zaglavlje,
  - faktura stavke,
  - naimenovanja,
  - nedostajuća obavezna polja.
- Dodan agent alat `pregled_stanja_aplikacije`.
- Dodan fallback za upite tipa:
  - "pogledaj tab faktura",
  - "pregledaj naimenovanja",
  - "šta je učitano",
  - "stanje aplikacije".
- Agent sada razumije konkretne reference:
  - "7 naimenovanje",
  - "sedmo naimenovanje",
  - "25 stavka u tabu faktura",
  - "ova stavka",
  - "taj broj".
- Popravljeni tokovi:
  - `Predloži tarifu za 7 naimenovanje` koristi stvarni opis robe iz tog naimenovanja.
  - `Pogledaj u bazi podataka za taj proizvod` koristi prethodno otvoreni proizvod.
  - `Provjeri stavku 25 u tabu faktura` vraća tačnu fakturnu liniju, ne sažetak cijelog taba.
  - `Predloži mi tarifni broj za ovu stavku` koristi posljednju otvorenu fakturnu stavku.
  - `21021000 ubaci ovaj tarifni broj i sačuvaj u bazi podataka za ubuduće` upisuje tarifu u posljednju otvorenu stavku i poziva snimanje mapiranja.
  - `Ubaci taj broj u tabelu tabu faktura` koristi posljednji zapamćeni tarifni broj.
- EUR.1 dijalog je prilagođen radu po fakturi:
  - red za svaku fakturu,
  - zemlja porijekla po fakturi,
  - povlastica po fakturi,
  - checkbox za EUR.1,
  - rubrika za EUR.1 broj,
  - veći fontovi i kompaktniji prozor.
- `FakturaView._assign_invoice_name()` više ne prepisuje broj fakture koji parser već isporuči.

## Testovi

Pokrenuto:

```bash
python -m pytest tests/unit/test_chat_context_followups.py tests/unit/test_application_context_service.py tests/unit/test_tariff_history_analysis_service.py tests/unit/test_similar_products_analysis_service.py tests/unit/test_product_similarity_memory_service.py tests/unit/test_product_similarity_embedding_service.py -q
```

Rezultat: `39 passed`.

Takođe ranije provjereni EUR1/PIP testovi:

```bash
python -m pytest tests/unit/test_application_context_service.py tests/unit/test_eur1_quick_dialog.py tests/unit/test_pip_food_parser.py -q
```

Rezultat: `10 passed`.

## Napomena

`AGENTS.md`, `CLAUDE.md` i postojeći untracked report `2026-05-21_mcp-i-gitnexus-fix.md` nisu dio ovog zadatka i nisu uključeni u commit.
