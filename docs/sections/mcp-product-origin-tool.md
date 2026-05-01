# MCP Product Origin Tool

## Svrha

Alat `find_product_origin` utvrđuje vjerovatnu zemlju porijekla proizvoda na osnovu
historijskih deklaracija u PostgreSQL bazi. Pretražuje `catalogs.declaration_items`
po opisu robe (ILIKE) i grupiše rezultate po zemlji porijekla.

Rezultat nije apsolutna istina — to je statistički prijedlog sa confidence skorom.
Ako nema pouzdanih nalaza, alat vraća `found=false` bez izmišljanja podataka.

## Zavisnosti i pretpostavke

- **Tabela:** `catalogs.declaration_items` (kolone: `naziv_robe`, `zemlja_porijekla`, `tarifni_broj`)
- **PostgreSQL ILIKE** za pretragu — nije full-text search (dovoljno za carinske nazive)
- **Pretpostavka:** Riječi kraće od 3 karaktera se ignorišu (prekratke za smislenu pretragu)
- **Pretpostavka:** Ako ukupan broj pogodaka nije nula, confidence se računa kao `broj_za_zemlju / ukupno`

## Pravila i granice

- Confidence nije mjera tačnosti — to je frekvencija u historijskim podacima
- Zemlja porijekla se **ne izmišlja** — ako nema podataka, `found=false`
- Tarifni brojevi se **ne predlažu** ovim alatom — samo zemlja porijekla
- Limit parametar se mora poštovati (max broj zemalja u rezultatu)
- Prazan ili whitespace-only input odmah vraća `found=false`
- `confidence` je uvijek između 0.0 i 1.0

## Zašto ovako

**Trade-off:** ILIKE pretraga umjesto pg_trgm ili full-text searcha. Razlog:
carinski nazivi su kratki, često sa brojevima i tehničkim oznakama. ILIKE je
dovoljan za ovu namjenu, a izbjegava dodatne PostgreSQL ekstenzije.

**Alternativa odbačena:** Koristiti `pg_trgm` za fuzzy matching — odbijeno jer
zahtijeva dodatnu ekstenziju i nije potrebno za uzorak "KONDENZATOR GCVC RD 045".

**Provjera:** Pokrenuti `test_product_origin_*` testove. Obratiti pažnju na:
- `test_no_results_for_nonsense` — mora vratiti `found=false`
- `test_limit_respected` — broj stavki ≤ limit
- `test_origin_never_invents_country` — prazni rezultati ne smiju sadržavati izmišljene zemlje
