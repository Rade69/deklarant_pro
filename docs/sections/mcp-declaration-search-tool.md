# MCP Declaration Search Tool

## Svrha

Alat `search_historical_declarations` pretražuje historijske stavke deklaracija po
opisu robe, sa opcionim filterima za zemlju porijekla, tarifni broj i izvoznika.

Za razliku od `find_product_origin` koji grupiše po zemlji, ovaj alat vraća
pojedinačne stavke — koristan je za istraživanje konkretnih slučajeva i pronalaženje
prethodnih deklaracija za sličnu robu.

## Zavisnosti i pretpostavke

- **Tabela:** `catalogs.declaration_items` (kolone: `tarifni_broj`, `naziv_robe`, `zemlja_porijekla`, `povlastica`, `declaration_id`)
- **Tabela:** `catalogs.declarations` (kolona: `vendor`) — samo ako se koristi `exporter_name` filter
- **Pretpostavka:** Riječi kraće od 3 karaktera se ignorišu
- **Pretpostavka:** JOIN sa `declarations` se radi samo kada je eksplicitno zatražen exporter filter

## Pravila i granice

- Svi filteri su opcioni — ako nijedan nije postavljen, pretraga je samo po opisu
- `hs_code` filter koristi LIKE sa prefiksom (npr. "8419" → "8419%")
- `country_code` filter zahtijeva tačan match (ILIKE nije potreban za ISO kodove)
- Limit parametar se mora poštovati
- Prazan query ili query bez pretraživih riječi odmah vraća prazan niz

## Zašto ovako

**Trade-off:** Dva odvojena alata za pretragu (`search_historical_declarations` i
`find_product_origin`) umjesto jednog generičkog. Razlog: različiti use-casevi
zahtijevaju različite grupacije i output formate. Origin alat grupiše po zemlji,
search alat vraća ravne stavke. Spajanje bi zakomplikovalo API bez dobitka.

**Alternativa odbačena:** Jedan alat sa `mode` parametrom ("origin" vs "search").
Odbijeno jer bi output schema varirala po modu, što otežava klijentsku validaciju.

**Provjera:** Pokrenuti `test_declaration_search_*` testove. Posebno:
- Test sa svim filterima istovremeno
- Test sa praznim filter dict-om
- SQL injection testovi
