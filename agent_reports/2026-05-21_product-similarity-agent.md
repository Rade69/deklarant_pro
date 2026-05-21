# Agent Report: Product similarity memorija i agent pretraga slicnih proizvoda

**Datum:** 2026-05-21
**Grana:** dev

---

## Problem

Agent je na upite o ranijim slicnim proizvodima znao vracati preopste istorijske
rezultate. Primjer je bio upit za DIXI bonbone/dekstrozu gdje su se pojavljivale
tarife za genericke bombone i cak nerelevantni proizvodi, jer je pretraga previse
nagradjivala opste rijeci poput "bomboni".

Drugi problem je bio routing: ako Tool Use ne izabere pravi alat, upit je mogao
otici u obicni chat i zaobici lokalnu analitiku.

---

## Rjesenje

Dodata je lokalna product similarity memorija nad PostgreSQL/pgvector tabelom
`catalogs.product_similarity_memory`.

Glavne komponente:

- migracija i sync iz `catalogs.product_tariff_mapping`
- embedding servis sa lokalnim default providerom
- agent alat `pronadji_slicne_proizvode`
- regex/deterministicki routing za upite tipa "upit o DIXI bonbonama"
- HTML izvjestaj koji grupise rezultate po tarifnom broju

Embedding provider je po defaultu lokalni:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Nazivi robe se ne salju eksternom provideru dok je `SEND_SENSITIVE_DATA=false`.
Lokalni 384-dimenzioni vektori se pune nulama do 1536 dimenzija da odgovaraju
PostgreSQL `vector(1536)` koloni.

---

## DIXI korekcija

Dodato je razlikovanje specificnih i generickih tokena.

Genericke forme kao:

- bombon
- bomboni
- bonbone
- bonbonama
- bombonima

vise ne postaju obavezni filter. Za upite tipa `DIXI bonbonama` obavezan signal
je `dixi`, pa genericki zapisi bez DIXI vise ne ulaze u rezultat.

Primjeri u tabeli se prikazuju oko specificnog tokena iz upita. Ako je DIXI
zakopan poslije dugog tarifnog opisa, UI sada prikazuje relevantni isjecak oko
DIXI dijela umjesto pocetka generickog opisa.

---

## Ponosanje nakon izmjene

Za upit:

```text
DIXI dekstroza bomboni
```

rezultat ostaje `KONFLIKT`, sto je namjerno i ispravno, jer istorija za DIXI
sadrzi vise tarifa. Agent ne donosi automatsku odluku, nego prikazuje analitiku:

- `21069092`
- `17049081`
- `21069098`

Nerelevantne grupe poput plastike i generickih bombona bez DIXI signala vise ne
treba da se prikazuju.

---

## Testovi i provjere

Provjereno:

```text
python -m py_compile \
  services/agent/learning/product_similarity_embedding_service.py \
  services/agent/chat/similar_products_analysis_service.py \
  gui/tabs/agent/services/chat_intent_handler.py \
  gui/tabs/agent/widgets/chat_panel.py

python -m pytest \
  tests/unit/test_product_similarity_embedding_service.py \
  tests/unit/test_product_similarity_memory_service.py \
  tests/unit/test_similar_products_analysis_service.py -q
```

Relevantni testovi prolaze.

GitNexus `detect_changes` je pokazan kao `medium` rizik zbog sireg dirty stanja
u radnom stablu, ne samo zbog ove izmjene.

---

## Napomene

Ovo je analiticki alat, ne automatski klasifikator tarife. Kada istorija ima vise
tarifa za isti ili slican proizvod, agent mora jasno prikazati konflikt i traziti
rucnu provjeru.
