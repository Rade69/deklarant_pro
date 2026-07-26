# AGENTS.md — Deklarant Pro projektni standardi (KANONSKI FAJL)

Ovaj fajl je **jedini izvor istine** za sve agente koji rade na ovom projektu:
Claude Code, Codex, Cursor, GitHub Copilot, DeepSeek, GLM, Kimi, MiniMax, Qwen i drugi.
`CLAUDE.md` u korijenu samo importuje ovaj fajl i dodaje Claude-specifičnu memoriju —
**sva pravila se mijenjaju OVDJE**, ne u CLAUDE.md.

---

## Jezik — OBAVEZNO I PRIMARNO

- Svi odgovori korisniku: **srpski, latinica**
- Nikada ćirilica — nigdje, ni u komentarima ni u stringovima koji se prikazuju
- Nikada engleski (osim ako korisnik eksplicitno traži)
- Komentari u kodu: engleski (prati stil koji fajl već koristi)
- Commit poruke: srpski latinica, format `tip(scope): opis`

---

## Kontekst projekta — pročitaj prije kodiranja

**OBAVEZNO: Pročitaj `docs/CONTEXT.md` prije bilo kakvog kodiranja.**

Taj fajl sadrži ne-trivijalne odluke, zabranjene patterne i poznate bugove
koji nisu vidljivi iz samog koda. Dostupan je svim agentima jer je u git repozitoriju.

```text
docs/CONTEXT.md   ← zajednička memorija za sve agente (Claude, Codex, DeepSeek...)
```

> **Samo za Claude:** detaljna sesijska memorija je u
> `~/.claude/projects/<projekat>/memory/` (vidi CLAUDE.md).
> Za sve ostale agente `docs/CONTEXT.md` je autoritativni izvor.

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš uraditi.
Čekaj potvrdu korisnika prije implementacije ako zadatak nije jednoznačan.

---

## Tech stack

| Sloj | Tehnologija |
| --- | --- |
| GUI | PySide6 (Qt6) |
| Baza | PostgreSQL 16 (server `dmserver`, IP je DHCP — čitati iz `.env` preko `config/settings.py`, ne hardkodovati) + SQLite lokalno |
| Python | 3.11+, uv za pakete |
| Testovi | pytest, `tests/` folder |
| Parseri | pdfplumber, openpyxl, pytesseract (OCR) |

---

## Arhitektura

```text
deklarant_pro/
├── core/draft/          # Draft modeli: DeclarationDraft, InvoiceLine, NaimenovanjeDraft
├── gui/tabs/            # GUI tabovi (agent_tab, faktura_tab, naimenovanja_tab...)
│   └── agent/
│       ├── agent_controller.py      # Tanak controller — samo 1-liner wrapper metode
│       └── services/                # Sva logika izvučena ovdje
│           ├── xml_workflow_service.py
│           ├── import_pipeline_service.py
│           └── chat_intent_handler.py
├── importers/           # PDF/Excel parseri po dobavljaču
├── services/            # Business logika
│   └── agent/
│       ├── chat/        # intent_classifier, chat_memory, namjere
│       ├── tariff/      # hybrid_tariff_agent, rag, matching
│       ├── learning/    # historical_learning, exporter_xml_indexer
│       └── validation/  # declaration_validator, xml_template_service
├── database/            # SQLite: deklarant_sistem.db, zvanicna_tarifa.db
├── dist_client/         # Windows-runtime kopija (može zaostati za gui/ — uporedi pri vizuelnim bugovima)
└── ui/                  # Qt .ui fajlovi
```

**Pattern za services/agent/:** slobodne funkcije koje primaju `ctrl` kao prvi argument,
servisna klasa ih omotava kao public API. Controller metode su samo 1-liner pozivi servisa.

### 3-layer pattern za tabove (OBAVEZNO)

Svaki tab/modul je podijeljen na tri sloja — **ne miješati slojeve**:

```text
View       — samo UI, signali, prikaz podataka, NEMA business logike
Controller — orchestration, event handling, povezuje View ↔ Service
Service    — sva business logika, DB operacije, kalkulacije
```

Signali su jedini ispravni način komunikacije prema gore (View ne poziva
Controller metode direktno). Business logika ili DB konekcija u View-u je greška.

---

## Ključne konvencije

### Kod

- **Nema novih komentara** osim za neočigledne workarounds ili skrivene invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
  (novi docstrings, gdje su stvarno potrebni, pišu se na srpskom latinici)
- Fuzzy matching threshold: `min_similarity = 0.92` (ne spuštati bez eksplicitnog razloga)
- SQL: isključivo parametrizovani upiti — nikad f-string u SQL-u
- Debug ispisi: emoji za vizualnu identifikaciju (🔍, ✅, ⚠️, 📝) — ali NIKAD direktno
  na stderr (cp1252 na Windowsu puca); koristiti logger
- Error handling: jasne poruke na srpskom

### Imenovanje polja — KRITIČNO

`InvoiceLine` i srodni modeli koriste **srpske nazive polja** — namjerno, ne mijenjati
na engleski (lomi sve importere): `tarifni_broj`, `naziv_robe`, `zemlja_porijekla`,
`povlastica`, `bruto_kg`, `neto_kg`, `iznos`, `kolicina`, `jm`, `eur1_number`.
Izuzetak: **NaimenovanjeDraft koristi engleski** (`tariff_code`, `goods_description`,
`origin_country_code`) — konzistentno s ASYCUDA XML formatom, takođe ne mijenjati.

### Tarifni broj format

- Interno **8 cifara bez tačaka**: `08052190`; PostgreSQL baza ima **10 cifara**: `0805219000`
- Konverzija pri PG lookup-u: dodati `'00'` na kraj
- Nikad ne čuvati format s tačkama (`0805.21.90`); normalizacija: `re.sub(r'\D', '', raw)[:10]`

### Formatiranje težina (bruto/neto kg)

- Puna preciznost (ne zaokruživati na 2 decimale)
- Separator za hiljade (zarez): `1,234.567`
- Referenca: `_format_weight()` u faktura_tab_v2.py

### Parseri (importers/)

- Svaki importer mora imati `exporter` i `importer` polja u `ImportResult`
- XML lookup se radi po paru `(exporter, tariff_code)` — ne samo po tariff_code
- CBBH kurs se čita iz baze, ne hardkoduje
- **Auto-detekcija formata**: svaki importer ima `detect_*` funkciju
- **Blagić Loren**: jedinica mjere može biti bilo koja riječ (regex: `[a-zA-Z]{1,10}`)
- **IMAMOGLU**: dvofazno parsiranje (kodovi/opisi na str. 1-2, cijene na str. 4-5)
- **Težine**: uvijek ekstraktovati gross/net weight iz PDF-a
- **Rezultat**: uvijek vraća `ImportResult` sa items, bruto_kg, neto_kg
- **OBAVEZNO — `consumed_paths`**: svaki kombinirani importer koji interno koristi drugi
  fajl (Excel+PDF par, Invoice+PackingList) MORA postaviti
  `consumed_paths=[putanja_potrošenog_fajla]` u `ImportResult`. Bez toga agent procesira
  oba fajla zasebno → duplikati stavki u deklaraciji.
  Primjer: CASE 1/2 (Blagić), CASE 1B/2B (Šumaprom), CASE 3/4 (Invoice+PackingList), Leburic.

### GUI konvencije

- **QTextEdit** za multi-line prikaze (ne QLineEdit)
- **Read-only polja** za auto-popunjene vrijednosti
- **Word wrap** omogućiti gdje je potrebno

### XML template (xml_template_service.py)

- Rb.48 (`odgodjeno_placanje`) se **ne prepisuje** iz historijskog XML-a — šifra se mijenja godišnje
- Mijenjati samo `TEMPLATE_FIELDS` whitelist — ne pisati ad-hoc logiku po polju

### Naimenovanja

- Rb.31 auto-opis se generiše po tarifi, ne prepisuje iz fakture
- **Trgovački naziv (`le_r31_trg_naziv`)**: prikazuje sve nazive proizvoda iz fakture koji
  pripadaju tom naimenovanju (comma-separated / multi-line, QTextEdit)
- ASYCUDA XML Rub.31 mora ostati max 280 znakova / 3 linije; skraćivanje raditi pri buildanju XML-a
- **Grupiranje po 4 ključa** (svi moraju biti identični): `tarifni_broj`, `zemlja_porijekla`,
  `povlastica`, `eur1_number` — koristiti `CreateNaimenovanjaService.create_smart_group()`,
  ne pisati vlastitu logiku grupiranja

### Auto-popunjavanje tarifnih brojeva

- **TariffMappingService**: mapiranje product_code/naziv_robe → tarifni_broj
- Matching prioritet: 1) tačan match po `product_code`, 2) fuzzy match po nazivu (>85%)
- Auto-učenje: sistem pamti mapiranja pri kreiranju naimenovanja
- Database: tabela `product_tariff_mapping` u deklarant_sistem.db
- ⚠️ Poznati obrazac buga: jedna ručna greška postane "naučen" trajni bug jer exact-match
  nadjača fuzzy logiku (3x viđeno: GREJAC SPIRALA, Plamenik 540101...)

### LLM / Agent integracija

- Primarni provider: Groq; fallback: Gemini (samo free modeli — DeepSeek isključen)
- Koristiti `LLMProvider` klasu (`gui/tabs/agent/widgets/llm_provider.py`) —
  **ne pozivati providere direktno** (zaobilazi fallback logiku)
- Streaming kroz `provider.stream_chat()`, batch kroz `provider.complete()`
- QThread workeri za sve LLM pozive — nikad blokirati UI thread

### Baza podataka

- `deklarant_sistem.db` (SQLite) — mappinzi, šifrarnici, lokalni podaci
- `zvanicna_tarifa.db` (SQLite) — samo čitanje, carinska tarifa
- PostgreSQL — `catalogs` schema; context manager (`with conn:`) za transakcije
- `blockSignals(True/False)` pri bulk operacijama na Qt tabelama (vidi CONTEXT.md §5)

---

## Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| Direktni `import` iz `gui/tabs/agent/agent_controller.py` u servis | Kružni import |
| Mijenjati `TEMPLATE_FIELDS` van `xml_template_service.py` | Single source of truth |
| Hardkodovati IP adresu servera u kodu | Mora biti u aktivnom `.env` fajlu (`root` ili `dist_client`, zavisno od pokretača) |
| Dodavati UI logiku u servisne klase | Narušava razdvajanje slojeva |
| Brisati stub fajlove u `services/agent/` bez provjere importa | Backward compat |
| f-string za QSS blokove | CSS `{}` puca u f-stringu — koristiti `.replace("PLACEHOLDER", ...)` |
| `return None` u `tab_factory`/`create_tab()` except bloku | Skriva greške — uvijek `raise` |
| Pozivati Groq/Gemini direktno bez `LLMProvider` | Nema fallback logike |
| Logika grupiranja naimenovanja van `CreateNaimenovanjaService` | Duplikacija, greške |
| Mijenjati srpske field names na modelima | Lomi sve importere |
| `mock` za SQLite/PostgreSQL u testovima | Maskira realne greške |
| Zaokruživati težine na 2 decimale | Gubi se preciznost pri carinskom obračunu |
| Miješati `draft.items` s `draft.invoice_lines` | Potpuno različiti koncepti |

---

## Format zadatka za agenta (preporučeno)

Za netrivijalne i debug zadatke, korisnik formuliše zadatak po ovom obrascu.
Agent ga prepoznaje i direktno mapira na sekcije agent reporta (Korak 3):

- **Zadatak** — šta treba popraviti/promijeniti
- **Moja radna pretpostavka** — korisnikova hipoteza o uzroku/rješenju
- **Provjeri hipotezu** — agent PRIJE izmjene potvrđuje ili odbacuje
  hipotezu dokazima (baza, kod, logovi) → puni "Zašto je urađeno" i
  "Verifikacija" u izvještaju
- **Granice** — šta agent NE smije dirati (van scope-a) → puni "Šta nije dirano"
- **Šta je dobar ishod** — opis vidljivog/testabilnog rezultata
- **Obavezno** — agent prikazuje impact/rizik i ostavlja agent_report
  → puni "GitNexus impact" i "Rizici / ograničenja"

Ovaj format je preporuka, ne zamjena za Korak 1-5: za sitne, jednolinijske
ispravke (npr. jedan red u bazi, jedna konstanta) format je nepotreban overhead.

---

## Plan prije izmjene — HIGH/CRITICAL GitNexus impact

Ako `gitnexus_impact` za simbol koji se mijenja vrati **HIGH** ili **CRITICAL**,
agent PRIJE izmjene napravi JEDAN kratki fajl (ne cijeli "project room"):

```
project_rooms/YYYY-MM-DD_kratak-naziv-zadatka.md
```

sa sekcijama:

- **Cilj** — šta se mijenja i zašto
- **Pogođeno** — simboli/procesi iz `gitnexus_impact` (broj, koji, rizik)
- **Plan** — fajlovi i redoslijed izmjena
- **Šta NE dirati** — eksplicitne granice (scope lock — vidi "Handoff visokog rizika" ispod)
- **Konflikti** — ako postoje kontradiktorni izvori (stari agent_report, memorija, kod),
  navesti oba, koji se tretira kao važeći i zašto, i da li je potrebna korisnička potvrda (DA/NE)

Fajl se na kraju može spojiti u `agent_report` (Korak 3) ili obrisati — nije trajna
dokumentacija. Za MEDIUM ili niži impact ovaj korak se preskače.

---

## Handoff visokog rizika (HIGH/CRITICAL GitNexus impact)

Kada `gitnexus_impact()` vrati `HIGH` ili `CRITICAL` rizik za simbol koji mijenjaš,
prijavi korisniku rizik u ovom formatu PRIJE izmjene (ne nakon):

> "GitNexus impact za `<simbol>` je `<risk>`: zavise od njega `<broj>` simbola/procesa
> (`<koji>`). Promjena je mala/velika po obimu ali `<visoka/niska>` po sistemskoj
> važnosti jer `<razlog>`. Scope ostaje ograničen na: `<šta NE diraš>`.
> Obavezni izlaz: `<šta MORA postojati — npr. ciljane izmjene + test pokrivenost>`."

Za svaku planiranu izmjenu odredi i navedi:

| Polje | Pitanje na koje odgovara |
| --- | --- |
| **Tip promjene** | bugfix / behavior adjustment / mapping correction / safety patch / refactor? |
| **Prihvatljiv ishod (scope lock)** | šta MORA ostati identično (npr. "validacija ostaje ista osim novog izvora dokaza") |
| **Nivo dozvole** | draft change only / no auto-merge / mandatory review / test gate required |

---

## ⚠️ OBAVEZNA PROCEDURA: nakon završenog zadatka (Korak 1-5)

Svaki agent MORA slijediti ovaj redosljed nakon što završi zadatak.
Git pre-commit hook (`scripts/git-hooks/pre-commit`) automatski sprovodi
py_compile provjeru i ispisuje podsjetnike — NE zaobilaziti ga sa `--no-verify`.

### Korak 1 — Git commit
- Staged promjene grupisati po logičkim cjelinama (ne sve u jedan commit)
- Format poruke: `tip(oblast): kratki opis` (`fix`, `feat`, `refactor`, `docs`, `chore`)
- Uvijek dodati `Co-Authored-By:` liniju sa imenom modela koji je radio
  (npr. `Co-Authored-By: Claude <noreply@anthropic.com>`)

### Korak 2 — Zajednička memorija
- Sve **ne-očigledno** i korisno za buduće sesije upisati u `docs/CONTEXT.md`
  (svi agenti) — Claude dodatno u svoju sesijsku memoriju (vidi CLAUDE.md)
- **Šta upisivati**: poslovne odluke, pravila koja nisu u kodu, bug uzroci, fiksevi koji se ponavljaju
- **Šta NE upisivati**: šta kod radi (vidi se iz koda), git historija, privremeno stanje

### Korak 3 — Agent report
- Kreirati izvještaj u `agent_reports/YYYY-MM-DD_naziv-zadatka.md` sa sekcijama (`##`):
  - **Datum**, **Agent**, **Scope** — fajlovi/moduli na koje se zadatak odnosi
  - **Status izvora** (samo kompleksni/rizični zadaci) — koji raniji
    agent_reports/memory/kod fajlovi su korišćeni i njihov status:
    aktivan / zastario / duplikat / treba potvrdu
  - **GitNexus impact** — rezultat provjere prije izmjene (rizik, broj pogođenih simbola/procesa)
  - **Šta je urađeno** — kratki pregled promjena
  - **Zašto je urađeno** — poslovni razlog, bug uzrok, odluka i alternativa
  - **Kako je urađeno** — tehnički pristup, koje funkcije/fajlovi
  - **Šta nije dirano** — eksplicitno navesti šta je OSTAVLJENO netaknuto
  - **Verifikacija** — kako je dokazano da promjena radi (testovi, offscreen provjere, py_compile...)
  - **Pronađeni problemi** — uključujući lažno pozitivne zaključke
  - **Konflikti / kontradiktorni izvori** (ako postoje) — koji je tretiran kao važeći
    i zašto, i da li treba korisnička potvrda (DA/NE)
  - **Commitovi** — tabela hash/poruka
  - **Rizici / ograničenja**
  - **Potreban follow-up** — šta NIJE zatvoreno
  - **Potrebna korisnička potvrda** — šta korisnik treba ručno provjeriti
- Commitovati izvještaj odmah nakon pisanja

### Korak 4 — Link u kodu (opcionalno, za kompleksne odluke)
- Kada je odluka netrivijalna, dodati komentar koji referiše na izvještaj:
  ```python
  # Vidi agent_reports/2026-05-09_naziv.md — objašnjenje odluke
  ```
- Samo gdje je stvarno potrebno, ne na svakoj promjeni

### Korak 5 — GitNexus ažuriranje
- Nakon commita provjeriti je li GitNexus index zastario
- Ako jeste: `npx gitnexus analyze`

---

## Testiranje

- Uvijek testirati sa pravim fakturama iz `najavauvoza/` foldera
- Debug ispisi moraju biti informativni i pregledni
- Provjeriti edge case-ove (bez kodova, multi-line opisi, različite jedinice)

---

## Format outputa

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

---

## Provjera prije predaje

- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] Nisam koristio string interpolaciju u SQL-u
- [ ] Testovi prolaze: `python -m pytest tests/ -q` (iz korijena projekta)
- [ ] Output format je popunjen (STATUS, IZMIJENJENI FAJLOVI, itd.)

## DOC Guard

Kada hook injektuje `[DOC-GUARD]` poruku:

- **BROKEN** → zaustavi se, ispravi putanju ili kreiraj MD fajl prema
  `.claude/DECISION_RECORD_TEMPLATE.md` — ne commitaj sa broken linkom
- **STALE** → procijeni: logička izmjena = ažuriraj MD; kozmetička = nastavi
- Ručna provjera: `bash scripts/doc_link_checker.sh .`

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deklarant_pro** (48790 symbols, 75164 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
