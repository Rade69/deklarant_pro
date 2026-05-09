# CLAUDE.md - Projektne instrukcije za AI asistenta

## ⚠️ JEZIK: ISKLJUČIVO SRPSKI LATINICA

**OVA INSTRUKCIJA JE OBAVEZNA I PRIMARNA:**
- Pišem isključivo na **srpskom jeziku, latinica**
- Svi odgovori, objašnjenja, komentari su na latinici
- Nikada ne pišem ćirilicom
- Nikada ne pišem na engleskom (osim ako korisnik eksplicitno traži)
- Kod komentari mogu biti na engleskom ako već postoje u kodu

---

## ⚠️ OBAVEZNO: Čitanje memorije na početku SVAKE sesije

**Kada me pozoveš, PRVO čitam memoriju projekta.**

### Automatsko određivanje projekta
- Ime projekta se određuje iz **working directory** ili **.claude/settings.json**
- Za ovaj projekt: **`deklarant_pro`**

### Protokol na početku sesije:

**1. Pozovi `get_project_overview`:**
```
project: "deklarant_pro"
```

**2. Pozovi `query_memory` sa relevantnim query-ima:**
```
project: "deklarant_pro"
query: "arhitektura tabovi refactor status"
```

**3. Dodatni query prema zadatku:**
- Refactoring → `"faktura zaglavlje service controller"`
- Bugovi → `"bugovi rješenja known issues"`
- GUI → `"GUI PySide6 tabovi layout"`
- Testovi → `"testovi coverage"}
```

### Šta memorija sadrži:
- ✅ Tab Refactor Pattern (3-layer: View/Controller/Service)
- ✅ ZaglavljeTab, FakturaTab, NaimenovanjaTab, SifarniciTab status
- ✅ Code reduction metrike (-12.6% ukupno)
- ✅ Safe refactoring decisions i lessons learned
- ✅ Bug history i poznata rješenja

### 📌 VAŽNO:
- Čitaj **SAMO memoriju vezanu za trenutni projekt**
- Ne čitaj flat MEMORY.md fajlove van projekta
- MCP memorija ima prvenstvo nad dokumentacijom

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
- **OBAVEZNO — `consumed_paths`**: Svaki kombinirani importer koji interno koristi drugi fajl
  (Excel+PDF par, Invoice+PackingList) MORA postaviti `consumed_paths=[putanja_potrošenog_fajla]`
  u `ImportResult`. Bez toga agent procesira oba fajla zasebno → duplikati stavki u deklaraciji.
  Primjer: CASE 1/2 (Blagić), CASE 1B/2B (Šumaprom), CASE 3/4 (Invoice+PackingList), Leburic.

### 6. Auto-popunjavanje tarifnih brojeva
- **TariffMappingService**: baza znanja za mapiranje product_code/naziv_robe → tarifni_broj
- **Matching prioritet**:
  1. Tačan match po `product_code`
  2. Fuzzy match po nazivu (>85% sličnosti)
- **Auto-učenje**: sistem automatski pamti mapiranja pri kreiranju naimenovanja
- **Dugme "Auto-popuni tarifne"**: automatski popuni poznate proizvode
- **Database**: tabela `product_tariff_mapping` u deklarant_sistem.db

## Stil koda

- Docstrings na srpskom latinici za nove metode
- Komentari mogu biti na engleskom za postojeći kod
- Print poruke: emoji za vizualnu identifikaciju
- Error handling: jasne poruke na srpskom

## Struktura projekta

```
deklarant_pro/
├── core/draft/          # Draft modeli (DeclarationDraft, InvoiceLine, NaimenovanjeDraft)
├── gui/tabs/            # GUI tabovi (faktura, naimenovanja, zaglavlje)
├── importers/           # PDF/Excel parseri za različite dobavljače
├── services/            # Business logika (import_service, tariff_service)
├── database/            # SQLite baze (deklarant_sistem.db, zvanicna_tarifa.db)
└── ui/                  # Qt .ui fajlovi
```

## Testiranje

- Uvijek testirati sa pravim fakturama iz `najavauvoza/` foldera
- Debug ispisi moraju biti informativni i pregledni
- Provjeriti edge case-ove (bez kodova, multi-line opisi, različite jedinice)

## Git konvencije

- Commit poruke na srpskom latinici
- Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>
- Opisati šta je promijenjeno i zašto

---

## ⚠️ OBAVEZNA PROCEDURA: Nakon završenog zadatka

Svaki agent koji radi na ovom projektu MORA slijediti ovaj redosljed nakon što završi zadatak:

### Korak 1 — Git commit
- Staged promjene grupisati po logičkim cjelinama (ne sve u jedan commit)
- Format poruke: `tip(oblast): kratki opis`
- Primjeri tipova: `fix`, `feat`, `refactor`, `docs`, `chore`
- Uvijek dodati: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

### Korak 2 — Memorija
- Upisati u memorijski fajl sve što je **ne-očigledno** i korisno za buduće sesije
- Lokacija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/`
- Format fajla: `YYYY-MM-DD_kratki-opis.md` sa YAML frontmatterom (`name`, `description`, `type`)
- Ažurirati `MEMORY.md` index — jedna linija po memorijskom fajlu
- **Šta upisivati**: poslovne odluke, pravila koja nisu u kodu, bug uzroci, fiksevi koji se mogu ponoviti
- **Šta NE upisivati**: šta kod radi (to se vidi iz koda), git historija, privremeno stanje

### Korak 3 — Agent report
- Kreirati izvještaj u `agent_reports/YYYY-MM-DD_naziv-zadatka.md`
- Izvještaj mora sadržavati:
  - **Šta** je urađeno (kratki pregled promjena)
  - **Kako** je urađeno (tehnički pristup, koje funkcije/fajlovi)
  - **Zašto** (poslovni razlog, bug uzrok, odluka i alternativa)
  - Tabelu commitova sa hashovima
- Commitovati izvještaj odmah nakon pisanja

### Korak 4 — Link u kodu (opcionalno, za kompleksne odluke)
- Kada je odluka netrivijalna (npr. zašto je odabran ovaj algoritam, zašto je nešto preskočeno), dodati komentar u kodu koji referiše na izvještaj:
  ```python
  # Vidi agent_reports/2026-05-09_naziv.md — objašnjenje odluke
  ```
- Koristiti samo gdje je stvarno potrebno, ne na svakoj promjeni

### Korak 5 — GitNexus ažuriranje
- Nakon commita provjeriti je li GitNexus index zastario
- Ako jeste, pokrenuti: `npx gitnexus analyze`

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deklarant_pro** (15049 symbols, 24405 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
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
