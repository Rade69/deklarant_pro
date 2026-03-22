# CLAUDE.md - Projektne instrukcije za AI asistenta

## ⚠️ VAŽNO: Čitanje memorije na početku SVAKE sesije

**Pri svakom novom zadatku / sesiji**, OBAVEZNO uradi oba koraka:

### Korak 1: Koristi MCP Memory Server (universal-memory) - PRVI KORAK
MCP server `universal-memory` je dostupan za projekat `asycuda_pro`.

**NA POČETKU SESIJE:**
1. Pozovi `get_project_overview(project="asycuda_pro")` - da dobiješ pregled svih memorija
2. Zatim koristi `query_memory(project="asycuda_pro", query="...")` za specifične teme

Primjeri query-ja:
- Arhitektura → `query_memory(project="asycuda_pro", query="arhitektura GUI tabovi 3-layer")`
- Refactoring → `query_memory(project="asycuda_pro", query="faktura zaglavlje refactor service view controller")`
- Bugovi → `query_memory(project="asycuda_pro", query="bugovi rješenja recursion")`
- Testovi → `query_memory(project="asycuda_pro", query="testovi coverage integration")`

### Korak 2: Pročitaj flat MEMORY.md indeks (ako postoji)
```
/home/radovan/.claude/projects/-home-radovan-Desktop-asycuda-pro/memory/MEMORY.md
```

**MCP memorija ima PRVENSTVO** - sadrži 13+ cells sa:
- Tab Refactor Pattern (View/Controller/Service)
- ZaglavljeTab, FakturaTab, NaimenovanjaTab, SifarniciTab status
- Code reduction metrike (-12.6% ukupno)
- Safe refactoring decisions i lessons learned

---

## Jezik i komunikacija

**VAŽNO**: Uvijek komuniciraj na **srpskom jeziku, latinica**.

- Sva objašnjenja, komentari i opisi promjena pišu se na srpskom latinici
- Kada pišeš šta radiš, koristi srpski latinicu
- Kada objašnjavaš probleme ili rješenja, koristi srpski latinicu
- Kod komentari mogu biti na engleskom ako već postoje u kodu, ali nova objašnjenja su na srpskom

## Projektne konvencije

### 1. Formatiranje težina (bruto/neto kg)
- Prikazivati sa **punom preciznošću** (ne zaokruživati na 2 decimale)
- Koristiti **separator za hiljade** (zarez): `1,234.567`
- Format: `_format_weight()` metoda u faktura_tab_v2.py

### 2. Parsiranje faktura
- **Blagić Loren**: jedinica mjere može biti bilo koja riječ (regex: `[a-zA-Z]{1,10}`)
- **IMAMOGLU**: dvofazno parsiranje (kodovi/opisi na str. 1-2, cijene na str. 4-5)
- **Težine**: uvijek ekstraktovati gross/net weight iz PDF-a

### 3. GUI konvencije
- **QTextEdit** koristiti za multi-line prikaze (ne QLineEdit)
- **Read-only polja** za auto-popunjene vrijednosti
- **Word wrap** omogućiti gdje je potrebno
- **Debug ispisi**: koristiti emoji za lakše praćenje (🔍, ✅, ⚠️, 📝)

### 4. Naimenovanja tab
- **Trgovački naziv (le_r31_trg_naziv)**: prikazuje sve nazive proizvoda iz fakture koji pripadaju tom naimenovanju
- Format: comma-separated, max 550 karaktera, skraćivanje sa "..."
- Koristi QTextEdit za multi-line prikaz

### 5. Import servisi
- **Auto-detekcija formata**: svaki importer ima detect_* funkciju
- **Kombinovanje**: Excel + PDF za Blagić (matching po product_code)
- **Rezultat**: uvijek vraća ImportResult sa items, bruto_kg, neto_kg

### 6. Auto-popunjavanje tarifnih brojeva
- **TariffMappingService**: baza znanja za mapiranje product_code/naziv_robe → tarifni_broj
- **Matching prioritet**:
  1. Tačan match po `product_code`
  2. Fuzzy match po nazivu (>85% sličnosti)
- **Auto-učenje**: sistem automatski pamti mapiranja pri kreiranju naimenovanja
- **Dugme "Auto-popuni tarifne"**: automatski popuni poznate proizvode
- **Database**: tabela `product_tariff_mapping` u asycuda_sistem.db

## Stil koda

- Docstrings na srpskom latinici za nove metode
- Komentari mogu biti na engleskom za postojeći kod
- Print poruke: emoji za vizualnu identifikaciju
- Error handling: jasne poruke na srpskom

## Struktura projekta

```
asycuda_pro/
├── core/draft/          # Draft modeli (DeclarationDraft, InvoiceLine, NaimenovanjeDraft)
├── gui/tabs/            # GUI tabovi (faktura, naimenovanja, zaglavlje)
├── importers/           # PDF/Excel parseri za različite dobavljače
├── services/            # Business logika (import_service, tariff_service)
├── database/            # SQLite baze (asycuda_sistem.db, zvanicna_tarifa.db)
└── ui/                  # Qt .ui fajlovi
```

## Testiranje

- Uvijek testirati sa pravim fakturama iz `najavauvoza/` foldera
- Debug ispisi moraju biti informativni i pregledni
- Provjeriti edge case-ove (bez kodova, multi-line opisi, različite jedinice)

## Git konvencije

- Commit poruke na srpskom latinici
- Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>
- Opisati šta je promijenjeno i zašto

---

*Ovaj fajl je kreiran da osigura konzistentnu komunikaciju i konvencije tokom razvoja projekta.*
