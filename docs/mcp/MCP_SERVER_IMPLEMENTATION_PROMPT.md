# Prompt za implementaciju MCP servera za Deklarant Pro

**Datum:** 2026-05-01  
**Namjena:** Prompt/specifikacija za agenta koji implementira MCP server za centralizovani pristup PostgreSQL bazi i carinskim alatima  
**Kontekst:** Deklarant Pro GUI ostaje PySide6 desktop aplikacija, a PostgreSQL baza je na zasebnom Ubuntu serveru

---

## Prompt

Implementiraj MCP server za Deklarant Pro kao zaseban servis na Ubuntu serveru na kojem se nalazi PostgreSQL baza. MCP server treba da bude siguran alatni sloj između desktop aplikacije/AI agenta i centralizovanih podataka. Ne pravi novi chat agent; MCP server treba da izlaže stabilne alate za carinske operacije, pretragu historije i validaciju.

### Cilj

Deklarant Pro trenutno ima dosta logike lokalno u GUI aplikaciji: pretraga historijskih XML deklaracija, tarifni mapping, porijeklo proizvoda, exporter XML lookup, validacija i helper logika za agent tab. Cilj MCP servera je da se ta logika postepeno centralizuje oko PostgreSQL baze, tako da desktop aplikacija poziva dobro definisane alate umjesto direktnog SQL-a ili lokalnih fajl-indexa.

MCP server mora omogućiti:
- sigurnu pretragu historijskih deklaracija,
- pretragu porijekla proizvoda,
- pretragu i prijedlog tarifnih brojeva iz historije i baze znanja,
- lookup XML templatea po izvozniku/uvozniku,
- prijedlog povlastice na osnovu zemlje i historije izvoznika,
- validaciju osnovnih deklaracijskih pravila koja zavise od baze.

### Arhitektonska pravila

1. MCP server je backend alatni servis, ne UI i ne chat agent.
2. Desktop aplikacija ostaje vlasnik korisničkog workflow-a i prikaza.
3. PostgreSQL je centralni izvor istine.
4. MCP alati ne smiju vraćati sirove SQL greške korisniku.
5. SQL mora biti parametrizovan. Nema f-string interpolacije u SQL-u.
6. Nema hardkodovanih kredencijala, IP adresa ili lozinki. Sve ide kroz env/config.
7. Alati vraćaju strukturisane JSON rezultate, ne HTML.
8. Svaki alat mora imati kratak, stabilan input/output ugovor i testove.
9. Ako se koristi fuzzy matching, prag `min_similarity = 0.92` ne spuštati bez eksplicitnog razloga.
10. MCP server ne smije mijenjati podatke osim kroz eksplicitno write alate koji su posebno odobreni.

### Predložena struktura

Napravi novi modul/folder, npr:

```text
mcp_server/
├── server.py
├── config.py
├── db.py
├── tools/
│   ├── declaration_search.py
│   ├── product_origin.py
│   ├── tariff_history.py
│   ├── exporter_template.py
│   ├── preference.py
│   └── validation.py
└── tests/
    ├── test_product_origin.py
    ├── test_declaration_search.py
    └── test_tool_contracts.py
```

Ako projekat već ima drugačiji pattern za servise, prilagodi strukturu postojećem stilu, ali zadrži razdvajanje:
- transport/MCP layer,
- tool definitions,
- business/query service,
- database access.

### Minimalni alati za prvu verziju

#### `find_product_origin`

Input:

```json
{
  "product_name": "KONDENZATOR GCVC RD 045.2/24-53",
  "limit": 10
}
```

Output:

```json
{
  "query": "KONDENZATOR GCVC RD 045.2/24-53",
  "found": true,
  "origins": [
    {
      "country_code": "IT",
      "count": 3,
      "confidence": 0.82,
      "examples": [
        {
          "hs_code": "84195080",
          "commercial_desc": "KONDENZATOR ...",
          "exporter_name": "..."
        }
      ]
    }
  ],
  "notes": []
}
```

Pravila:
- Prvo traži tačan/sličan naziv u historijskim deklaracijama.
- Ako nema pouzdanih nalaza, `found=false`, bez izmišljanja porijekla.
- Ne predlagati tarifu ako korisnik traži isključivo porijeklo, osim kao kontekst u `examples`.

#### `search_historical_declarations`

Input:

```json
{
  "query": "kondenzator GCVC",
  "filters": {
    "country_code": "",
    "hs_code": "",
    "exporter_name": ""
  },
  "limit": 20
}
```

Output:

```json
{
  "results": [
    {
      "hs_code": "84195080",
      "commercial_desc": "...",
      "country_origin": "IT",
      "preference": "EUP",
      "exporter_name": "...",
      "declaration_ref": "..."
    }
  ]
}
```

#### `suggest_tariff_from_history`

Input:

```json
{
  "product_name": "KONDENZATOR GCVC RD 045.2/24-53",
  "exporter_name": "",
  "country_code": "",
  "limit": 5
}
```

Output:

```json
{
  "suggestions": [
    {
      "hs_code": "84195080",
      "confidence": 0.88,
      "source": "historical",
      "reason": "Slični kondenzatori ranije deklarisani pod ovim tarifnim brojem"
    }
  ],
  "needs_review": true
}
```

Pravila:
- Ovo je prijedlog, ne automatska odluka.
- Ako je confidence nizak, postaviti `needs_review=true`.
- Ne vraćati lažnu sigurnost.

#### `find_exporter_xml_template`

Input:

```json
{
  "exporter_name": "...",
  "consignee_jib": "...",
  "consignee_name": "..."
}
```

Output:

```json
{
  "found": true,
  "match_type": "exporter_consignee",
  "xml_template_id": "...",
  "source_filename": "..."
}
```

Pravila:
- XML lookup se radi po paru `(exporter, consignee)` gdje god je moguće.
- Ne vraćati cijeli XML ako nije potrebno; vratiti ID/metadata, a sadržaj samo kroz poseban alat.

#### `suggest_preference`

Input:

```json
{
  "country_code": "TR",
  "exporter_name": "..."
}
```

Output:

```json
{
  "preference": "TRP",
  "confidence": 0.9,
  "source": "historical_country_exporter",
  "requires_origin_document": true
}
```

Pravila:
- CBBH kurs i carinska pravila ne hardkodovati u MCP alatima.
- Ako nema historije, vratiti `confidence=0` i `preference=""`.

#### `validate_declaration_summary`

Input:

```json
{
  "draft_summary": {
    "item_count": 99,
    "invoice_total": 1234.56,
    "currency": "EUR",
    "items": []
  }
}
```

Output:

```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

Pravila:
- Blokirati više od 99 naimenovanja po deklaraciji.
- Ne preuzimati kompletnu GUI validaciju u prvoj verziji; početi sa pravilima koja zavise od baze i centralnih šifarnika.

### Integracija sa postojećim Deklarant Pro kodom

Prva integracija treba biti uska:

1. Dodati MCP client adapter u aplikaciji.
2. Agent Tool Use routing neka i dalje odlučuje korisničku namjeru.
3. Za alate koji imaju MCP ekvivalent, pozvati MCP umjesto lokalne implementacije.
4. Ako MCP nije dostupan, koristiti postojeći lokalni fallback gdje postoji.
5. Ne uklanjati lokalne servise dok MCP alat nema testove i stabilan ugovor.

Prioritet integracije:

1. `find_product_origin`
2. `search_historical_declarations`
3. `suggest_tariff_from_history`
4. `find_exporter_xml_template`
5. `suggest_preference`
6. `validate_declaration_summary`

### Dokumentacija koju moraš dodati

Za svaku veću cjelinu dodaj section dokument po pravilima iz:

```text
docs/agent_code/AGENT_CODE_DOC.md
```

Minimalno dodati:

```text
docs/sections/mcp-server-architecture.md
docs/sections/mcp-product-origin-tool.md
docs/sections/mcp-declaration-search-tool.md
```

U kodu dodati sekcijske oznake:

```python
# ============================================================
# SECTION: mcp-product-origin-tool
# PURPOSE: Exposes safe product origin lookup from historical declarations
# DOC: docs/sections/mcp-product-origin-tool.md
# ============================================================
```

### Testovi

Obavezni testovi:
- alat vraća `found=false` kada nema nalaza,
- alat ne izmišlja zemlju porijekla,
- SQL injection pokušaj ostaje bez efekta,
- limit parametar se poštuje,
- više od 99 naimenovanja daje validation error,
- MCP alat vraća stabilan JSON schema za happy path i empty path.

Ako integraciona PostgreSQL baza nije dostupna u test okruženju, izdvojiti query builder i schema validation u unit testove, a integracione testove označiti jasno kao integration.

### Kriterij završetka

Implementacija je prihvatljiva tek kada:
- MCP server može lokalno startovati,
- minimalni alati imaju testove,
- nema direktnog SQL-a iz GUI agenta za nove MCP tokove,
- postoji dokumentacija u `docs/sections`,
- postoji primjer konfiguracije bez tajni,
- fallback ponašanje je jasno dokumentovano,
- `python -m pytest` za relevantne testove prolazi.

### Ne raditi u prvoj verziji

- Ne migrirati cijelu aplikaciju odjednom.
- Ne brisati postojeće lokalne servise.
- Ne praviti novi chat UI.
- Ne stavljati LLM prompt logiku u MCP server.
- Ne uvoditi write alate dok read-only alati ne budu stabilni.
- Ne hardkodovati server IP, kredencijale ili nazive privatnih fajlova.

---

## Napomena za agenta koji implementira

Ovo je backend infrastrukturni zadatak. Najveći rizik nije pisanje MCP servera, nego miješanje odgovornosti:
MCP server treba da bude pouzdan carinski alatni backend, a ne još jedan sloj koji razgovara sa korisnikom.
Ako si u dilemi, zadrži MCP alat jednostavan, strukturisan i testabilan.
