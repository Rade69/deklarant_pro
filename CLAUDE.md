# CLAUDE.md - Projektne instrukcije za AI asistenta

## âš ï¸ JEZIK: ISKLJUÄŒIVO SRPSKI LATINICA

**OVA INSTRUKCIJA JE OBAVEZNA I PRIMARNA:**
- PiÅ¡em iskljuÄivo na **srpskom jeziku, latinica**
- Svi odgovori, objaÅ¡njenja, komentari su na latinici
- Nikada ne piÅ¡em Ä‡irilicom
- Nikada ne piÅ¡em na engleskom (osim ako korisnik eksplicitno traÅ¾i)
- Kod komentari mogu biti na engleskom ako veÄ‡ postoje u kodu

---

## âš ï¸ OBAVEZNO: ÄŒitanje memorije na poÄetku SVAKE sesije

**Kada me pozoveÅ¡, PRVO Äitam memoriju projekta.**

### Automatsko odreÄ‘ivanje projekta
- Ime projekta se odreÄ‘uje iz **working directory** ili **.claude/settings.json**
- Za ovaj projekt: **`deklarant_pro`**

### Protokol na poÄetku sesije:

**1. Pozovi `get_project_context`:**
```
project_id: "deklarant_pro"
```

**2. Pozovi `search_project_memory` sa relevantnim query-ima:**
```
project_id: "deklarant_pro"
query: "arhitektura tabovi refactor status"
```

**3. Dodatni query prema zadatku:**
- Refactoring â†’ `"faktura zaglavlje service controller"`
- Bugovi â†’ `"bugovi rjeÅ¡enja known issues"`
- GUI â†’ `"GUI PySide6 tabovi layout"`
- Testovi â†’ `"testovi coverage"}
```

### Å ta memorija sadrÅ¾i:
- âœ… Tab Refactor Pattern (3-layer: View/Controller/Service)
- âœ… ZaglavljeTab, FakturaTab, NaimenovanjaTab, SifarniciTab status
- âœ… Code reduction metrike (-12.6% ukupno)
- âœ… Safe refactoring decisions i lessons learned
- âœ… Bug history i poznata rjeÅ¡enja

### ðŸ“Œ VAÅ½NO:
- ÄŒitaj **SAMO memoriju vezanu za trenutni projekt**
- Ne Äitaj flat MEMORY.md fajlove van projekta
- MCP memorija ima prvenstvo nad dokumentacijom

---

## Jezik i komunikacija

**VAÅ½NO**: Uvijek komuniciraj na **srpskom jeziku, latinica**.

- Sva objaÅ¡njenja, komentari i opisi promjena piÅ¡u se na srpskom latinici
- Kada piÅ¡eÅ¡ Å¡ta radiÅ¡, koristi srpski latinicu
- Kada objaÅ¡njavaÅ¡ probleme ili rjeÅ¡enja, koristi srpski latinicu
- Kod komentari mogu biti na engleskom ako veÄ‡ postoje u kodu, ali nova objaÅ¡njenja su na srpskom

## Projektne konvencije

### 1. Formatiranje teÅ¾ina (bruto/neto kg)
- Prikazivati sa **punom preciznoÅ¡Ä‡u** (ne zaokruÅ¾ivati na 2 decimale)
- Koristiti **separator za hiljade** (zarez): `1,234.567`
- Format: `_format_weight()` metoda u faktura_tab_v2.py

### 2. Parsiranje faktura
- **BlagiÄ‡ Loren**: jedinica mjere moÅ¾e biti bilo koja rijeÄ (regex: `[a-zA-Z]{1,10}`)
- **IMAMOGLU**: dvofazno parsiranje (kodovi/opisi na str. 1-2, cijene na str. 4-5)
- **TeÅ¾ine**: uvijek ekstraktovati gross/net weight iz PDF-a

### 3. GUI konvencije
- **QTextEdit** koristiti za multi-line prikaze (ne QLineEdit)
- **Read-only polja** za auto-popunjene vrijednosti
- **Word wrap** omoguÄ‡iti gdje je potrebno
- **Debug ispisi**: koristiti emoji za lakÅ¡e praÄ‡enje (ðŸ”, âœ…, âš ï¸, ðŸ“)

### 4. Naimenovanja tab
- **TrgovaÄki naziv (le_r31_trg_naziv)**: prikazuje sve nazive proizvoda iz fakture koji pripadaju tom naimenovanju
- Format u GUI-u: comma-separated / multi-line pregled; ASYCUDA XML Rub.31 izlaz mora ostati max 280 karaktera / 3 linije, skraÄ‡ivanje pri buildanju XML-a
- Koristi QTextEdit za multi-line prikaz

### 5. Import servisi
- **Auto-detekcija formata**: svaki importer ima detect_* funkciju
- **Kombinovanje**: Excel + PDF za BlagiÄ‡ (matching po product_code)
- **Rezultat**: uvijek vraÄ‡a ImportResult sa items, bruto_kg, neto_kg
- **OBAVEZNO â€” `consumed_paths`**: Svaki kombinirani importer koji interno koristi drugi fajl
  (Excel+PDF par, Invoice+PackingList) MORA postaviti `consumed_paths=[putanja_potroÅ¡enog_fajla]`
  u `ImportResult`. Bez toga agent procesira oba fajla zasebno â†’ duplikati stavki u deklaraciji.
  Primjer: CASE 1/2 (BlagiÄ‡), CASE 1B/2B (Å umaprom), CASE 3/4 (Invoice+PackingList), Leburic.

### 6. Auto-popunjavanje tarifnih brojeva
- **TariffMappingService**: baza znanja za mapiranje product_code/naziv_robe â†’ tarifni_broj
- **Matching prioritet**:
  1. TaÄan match po `product_code`
  2. Fuzzy match po nazivu (>85% sliÄnosti)
- **Auto-uÄenje**: sistem automatski pamti mapiranja pri kreiranju naimenovanja
- **Dugme "Auto-popuni tarifne"**: automatski popuni poznate proizvode
- **Database**: tabela `product_tariff_mapping` u deklarant_sistem.db

## Stil koda

- Docstrings na srpskom latinici za nove metode
- Komentari mogu biti na engleskom za postojeÄ‡i kod
- Print poruke: emoji za vizualnu identifikaciju
- Error handling: jasne poruke na srpskom

## Struktura projekta

```
deklarant_pro/
â”œâ”€â”€ core/draft/          # Draft modeli (DeclarationDraft, InvoiceLine, NaimenovanjeDraft)
â”œâ”€â”€ gui/tabs/            # GUI tabovi (faktura, naimenovanja, zaglavlje)
â”œâ”€â”€ importers/           # PDF/Excel parseri za razliÄite dobavljaÄe
â”œâ”€â”€ services/            # Business logika (import_service, tariff_service)
â”œâ”€â”€ database/            # SQLite baze (deklarant_sistem.db, zvanicna_tarifa.db)
â””â”€â”€ ui/                  # Qt .ui fajlovi
```

## Testiranje

- Uvijek testirati sa pravim fakturama iz `najavauvoza/` foldera
- Debug ispisi moraju biti informativni i pregledni
- Provjeriti edge case-ove (bez kodova, multi-line opisi, razliÄite jedinice)

## Git konvencije

- Commit poruke na srpskom latinici
- Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>
- Opisati Å¡ta je promijenjeno i zaÅ¡to

---

## âš ï¸ OBAVEZNA PROCEDURA: Nakon zavrÅ¡enog zadatka

Svaki agent koji radi na ovom projektu MORA slijediti ovaj redosljed nakon Å¡to zavrÅ¡i zadatak:

### Korak 1 â€” Git commit
- Staged promjene grupisati po logiÄkim cjelinama (ne sve u jedan commit)
- Format poruke: `tip(oblast): kratki opis`
- Primjeri tipova: `fix`, `feat`, `refactor`, `docs`, `chore`
- Uvijek dodati: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

### Korak 2 â€” Memorija
- Upisati u memorijski fajl sve Å¡to je **ne-oÄigledno** i korisno za buduÄ‡e sesije
- Lokacija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/`
- Format fajla: `YYYY-MM-DD_kratki-opis.md` sa YAML frontmatterom (`name`, `description`, `type`)
- AÅ¾urirati `MEMORY.md` index â€” jedna linija po memorijskom fajlu
- **Å ta upisivati**: poslovne odluke, pravila koja nisu u kodu, bug uzroci, fiksevi koji se mogu ponoviti
- **Å ta NE upisivati**: Å¡ta kod radi (to se vidi iz koda), git historija, privremeno stanje

### Korak 3 â€” Agent report
- Kreirati izvjeÅ¡taj u `agent_reports/YYYY-MM-DD_naziv-zadatka.md`
- IzvjeÅ¡taj mora sadrÅ¾avati:
  - **Å ta** je uraÄ‘eno (kratki pregled promjena)
  - **Kako** je uraÄ‘eno (tehniÄki pristup, koje funkcije/fajlovi)
  - **ZaÅ¡to** (poslovni razlog, bug uzrok, odluka i alternativa)
  - Tabelu commitova sa hashovima
- Commitovati izvjeÅ¡taj odmah nakon pisanja

### Korak 4 â€” Link u kodu (opcionalno, za kompleksne odluke)
- Kada je odluka netrivijalna (npr. zaÅ¡to je odabran ovaj algoritam, zaÅ¡to je neÅ¡to preskoÄeno), dodati komentar u kodu koji referiÅ¡e na izvjeÅ¡taj:
  ```python
  # Vidi agent_reports/2026-05-09_naziv.md â€” objaÅ¡njenje odluke
  ```
- Koristiti samo gdje je stvarno potrebno, ne na svakoj promjeni

### Korak 5 â€” GitNexus aÅ¾uriranje
- Nakon commita provjeriti je li GitNexus index zastario
- Ako jeste, pokrenuti: `npx gitnexus analyze`

---

## DOC Guard

Kada hook injektuje `[DOC-GUARD]` poruku:

- **BROKEN** â†’ zaustavi se, ispravi putanju ili kreiraj MD fajl prema
  `.claude/DECISION_RECORD_TEMPLATE.md` â€” ne commitaj sa broken linkom
- **STALE** â†’ procijeni: logiÄka izmjena = aÅ¾uriraj MD; kozmetiÄka = nastavi
- RuÄna provjera: `bash scripts/doc_link_checker.sh .`

---

<!-- gitnexus:start -->
# GitNexus â€” Code Intelligence

This project is indexed by GitNexus as **deklarant_pro** (37575 symbols, 59350 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol â€” callers, callees, which execution flows it participates in â€” use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace â€” use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/deklarant_pro/context` | Codebase overview, check index freshness |
| `gitnexus://repo/deklarant_pro/clusters` | All functional areas |
| `gitnexus://repo/deklarant_pro/processes` | All execution flows |
| `gitnexus://repo/deklarant_pro/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

