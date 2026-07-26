# Faza 0 — Baseline, inventar i zaključavanje ponašanja

**Plan**: `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` §8
**Datum**: 2026-07-26
**Agent**: Pi
**Status**: Završena

---

## 1. Mapa svih routing ulaza (10 slojeva, po redoslijedu)

Svi slojevi u `gui/tabs/agent/services/chat_intent_handler.py::_handle_message()`:

| # | Sloj | Linija | Tip | Šta radi |
|---|------|--------|-----|----------|
| 1 | `check_injection()` | 1009 | Sigurnost | Blokira zlonamjerne unose |
| 2 | `_resolve_followup()` | 1016 | Kontekst | Follow-up poruke ("šta je sa stavkom 5?") |
| 3 | `_resolve_contextual_request()` | 1020 | Kontekst | Kontekstualni zahtjevi |
| 4 | `_application_context_scope()` | 1024 | ⚠️ Keyword prečica | "pregledaj/pokaži + faktura/naimenovanja" → snapshot |
| 5 | `_is_naimenovanja_review_request()` | 1031 | ⚠️ Lokalni regex | Naimenovanja: prikaz vs validacija |
| 6 | `_extract_origin_product_query()` | 1040 | Lokalni regex | Pretraga porijekla |
| 7 | POTVRDA/OTKAZI pending | 1048 | Stanje | Potvrda/otkazivanje pending akcije |
| 8 | `_extract_similar_product_query()` | 1061 | Lokalni regex | Slični proizvodi |
| 9 | `ToolDispatcherWorker` | 1075 | 🔵 LLM Tool Use | Primarni — Groq → Gemini, bira alat |
| 10 | `_handle_message_regex_fallback()` | 1098 | ⚠️ Regex fallback | 335 linija regex-a → ChatWorker |

**Ključni problem**: Slojevi 4 i 5 presreću poruke PRIJE Tool Use-a (sloj 9). Ako lokalna regex prečica pogrešno klasifikuje poruku, Tool Use nikada ne dobija šansu.

---

## 2. Potvrđeni bugovi u routing-u

### 2.1 "Pregledaj" = SHOW (treba VALIDATE)

- **Fajl:Linija**: `chat_intent_handler.py:760-785`
- **Opis**: `_application_context_scope()` koristi ISTI keyword set za "pregledaj" (VALIDATE po planu §7) i "pokaži/prikaži" (SHOW). Rezultat: "Pregledaj Faktura tab" → `_pregled_stanja_aplikacije` (samo snapshot), umjesto validacije.
- **Dokaz**:
  ```python
  wants_view = any(kw in msg for kw in (
      "pogledaj", "pregledaj", "pokaži", "pokazi", "prikaži", "prikazi", ...
  ))
  ```
  "pregledaj" je u istoj listi kao "pokaži" — nema razlikovanja.

### 2.2 "Provjeri tabelu u tabu Faktura" — nepredvidivo

- **Opis**: "provjeri" NIJE u `wants_view` keyword setu, pa `_application_context_scope` NE presreće ovu poruku. Ali `_is_naimenovanja_review_request` takođe ne (nema "naim" keyword). Poruka ide u Tool Use (sloj 9) — što je ISPRAVNO, ali krhko: ako se doda novi keyword u `_application_context_scope`, može slučajno presresti.
- **Rizik**: Svaka izmjena `wants_view` keyworda može slučajno presresti VALIDATE poruke.

### 2.3 Sloj 4 i sloj 5 se preklapaju za "naimenovanja"

- **Opis**: "Prikaži naimenovanja" može biti presretnuto i od sloja 4 (`_application_context_scope`) i od sloja 5 (`_is_naimenovanja_review_request`). Sloj 4 se provjerava PRVI — ako ima i "faktura" i "naimenovanja" keyword, sloj 4 pobjeđuje.

### 2.4 Regex fallback (335 linija) — krhko i neodrživo

- **Opis**: `_handle_message_regex_fallback` je 335 linija regex koda koji pokriva stare tokove. Plan kaže da se briše kad Tool Use bude stabilan (001-tool-use-refactoring.md). Ovo je poznati dug — nije nov nalaz.

---

## 3. Karakterizacioni test fixture

Prema planu §8: `tests/fixtures/agent/intent_routing_cases.json` sa 50+ slučajeva.

Svaki slučaj dokumentuje **trenutno** ponašanje (koje možda nije ispravno).
Kada se implementira Faza 1, neki od ovih slučajeva će promijeniti expected.

Najvažniji slučajevi (plan §7 — kanonska matrica):

| # | Poruka | Trenutno ide u | Očekivano (plan) |
|---|--------|---------------|------------------|
| 1 | `Prikaži Faktura tab` | `_pregled_stanja_aplikacije` (SHOW) | SHOW ✅ |
| 2 | `Pregledaj Faktura tab` | `_pregled_stanja_aplikacije` (SHOW) | VALIDATE ❌ |
| 3 | `Provjeri tabelu u tabu Faktura` | Tool Use → verovatno VALIDATE | VALIDATE ✅ |
| 4 | `Šta je učitano?` | `_pregled_stanja_aplikacije` (SHOW) | SHOW ✅ |
| 5 | `Pregledaj naimenovanja` | `_pregledaj_naimenovanja` (SHOW) | VALIDATE ❌ |
| 6 | `Provjeri naimenovanje 5` | `_provjeri_naimenovanja` (VALIDATE) | VALIDATE ✅ |
| 7 | `Prikaži naimenovanja` | `_pregledaj_naimenovanja` (SHOW) | SHOW ✅ |
| 8 | `Provjeri tarife` | Tool Use → `provjeri_tarife` | VALIDATE ✅ |
| 9 | `Provjeri zaglavlje` | Tool Use → verovatno validacija | VALIDATE ✅ |
| 10 | `Provjeri deklaraciju` | Tool Use → `validuj_deklaraciju` | VALIDATE ✅ |
| 11 | `Da li je spremno za XML?` | Tool Use → verovatno validacija | VALIDATE ✅ |
| 12 | `Pogledaj stavku 17` | `_pregled_stanja_aplikacije` (SHOW) | SHOW ✅ |
| 13 | `Analiziraj tarife` | Tool Use → verovatno analiza | ANALYZE ✅ |
| 14 | `Predloži tarife za stavku 3` | Tool Use → `predlozi_tarife` | PROPOSE ✅ |
| 15 | `Spoji naimenovanja` | Tool Use → `spoji_naimenovanja` | MUTATE ✅ |

---

## 4. Implementation — Test fixture fajl

Kreirano `tests/fixtures/agent/intent_routing_cases.json` sa 50 slučajeva.
Kreiran test `tests/unit/test_agent_intent_routing_baseline.py` koji učitava
fixture i provjerava trenutno routing ponašanje.

NAPOMENA: Ovi testovi NE testiraju cijeli `_handle_message` flow (jer zahtijeva
LLM provider). Testiraju SAMO lokalne routing slojeve (1-8) koji su deterministički.
Tool Use (sloj 9) se mock-uje.

---

## 5. Početno stanje

- Grana: `windows` (commit `749676e`)
- GitNexus: svjež (reindeksiran 26.7.2026)
- `git status`: samo untracked fajlovi (nepovezani)
- Testovi: 1128 passed, 5 xfailed, 1 failed + 1 error (nepovezani)
