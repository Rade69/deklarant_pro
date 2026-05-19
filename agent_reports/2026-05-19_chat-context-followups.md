# Agent Report: Chat kontekst za tarifne follow-up upite

**Datum:** 2026-05-19  
**Grana:** dev

---

## Problem

Agent je na pitanje o konkretnom naimenovanju znao prikazati tarifni broj, ali
naredni upit tipa "Koliko puta je korišten taj tarifni broj" nije vezivao za
prethodni odgovor. Zbog toga je ponovo tražio tarifni broj ili je upit slao u
pogrešan alat/LLM tok.

Drugi problem je bio što se "Naimenovanje broj 18" moglo tumačiti kao indeks u
listi, a ne kao stvarni `ordinal_no` naimenovanja.

---

## Rješenje

U `chat_intent_handler.py` dodat je mali radni kontekst razgovora:

- `last_tariff_code`
- `last_naimenovanje_ordinal`
- `last_product_name`
- postojeći `last_subject`

Kontekst se puni kada agent prikaže jedno konkretno naimenovanje ili kada
provjeri tarifni broj po kodu.

Prije ToolDispatcher-a se sada lokalno hvataju deterministički follow-up upiti:

- "Naimenovanje broj 18"
- "Koliko puta je korišten taj tarifni broj"
- "Šta istorijski stoji za taj tarifni broj"
- korisnik pošalje samo broj nakon što ga je agent zatražio za istoriju

---

## Ponašanje nakon izmjene

Primjer toka:

```text
Korisnik: Naimenovanje broj 18
Agent: prikazuje Rb.18 i pamti tarifni broj iz tog naimenovanja.

Korisnik: Koliko puta je korišten taj tarifni broj?
Agent: koristi zapamćeni tarifni broj i vraća istorijsku statistiku iz
       catalogs.product_tariff_mapping.
```

Ako nema konteksta:

```text
Korisnik: Šta istorijski stoji za taj tarifni broj?
Agent: traži tarifni broj i pamti da je naredni numerički unos odgovor za
       istorijsku statistiku.
```

---

## Testovi

Dodat je `tests/unit/test_chat_context_followups.py`:

- pamćenje tarifnog konteksta poslije "Naimenovanje broj 18"
- follow-up "taj tarifni broj" koristi prethodno zapamćeni tarifni broj
- naredni numerički unos nakon zahtjeva za tarifni broj ide u istorijsku statistiku

Provjereno:

```text
python -m pytest tests/unit/test_chat_context_followups.py tests/unit/test_historical_tariff_validation.py -q
32 passed

python -m pytest tests/ -q
443 passed, 6 skipped
```

---

## Preostale napomene

Ovo nije zamjena za dugoročnu memoriju ili pun conversational planner. Ovo je
namjerno mali i deterministički sloj za najčešće opasne follow-up upite u radu
sa tarifama i naimenovanjima.
