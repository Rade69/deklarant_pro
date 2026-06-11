# AGENTS.md — Deklarant Pro projektni standardi

Ovaj fajl čitaju svi agenti koji rade na ovom projektu: Qwen Code, GitHub Copilot, Cursor,
MiniMax, CLI agenti i drugi. Dopunjuje globalni `~/.claude/AGENTS.md` — ne zamjenjuje ga.

---

## Kontekst projekta — pročitaj prije kodiranja

**OBAVEZNO: Pročitaj `docs/CONTEXT.md` prije bilo kakvog kodiranja.**

Taj fajl sadrži ne-trivijalne odluke, zabranjene patterne i poznate bugove
koji nisu vidljivi iz samog koda. Dostupan je svim agentima jer je u git repozitoriju.

```text
docs/CONTEXT.md   ← zajednička memorija za sve agente (Claude, Qwen, DeepSeek...)
```

Klauza `CLAUDE.md` u korijenu projekta sadrži formatske konvencije i projektne standarde.
Pročitaj je ako radiš šire izmjene ili nisi siguran u konvencije.

> **Samo za Claude:** Detaljne sesijske bilješke nalaze se i u
> `~/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/`
> ali `docs/CONTEXT.md` je autoritativni izvor za sve agente.

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš uraditi.
Čekaj potvrdu korisnika prije implementacije ako zadatak nije jednoznačan.

---

## Jezik

- Svi odgovori korisniku: **srpski, latinica**
- Komentari u kodu: engleski (prati stil koji fajl već koristi)
- Nikada ćirilica — nigdje, ni u komentarima ni u stringovima koji se prikazuju
- Commit poruke: srpski latinica, format `tip(scope): opis`

---

## Tech stack

| Sloj | Tehnologija |
| --- | --- |
| GUI | PySide6 (Qt6) |
| Baza | PostgreSQL 16 (server 192.168.0.69) + SQLite lokalno |
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
└── ui/                  # Qt .ui fajlovi
```

**Pattern za services/agent/:** slobodne funkcije koje primaju `ctrl` kao prvi argument,
servisna klasa ih omotava kao public API. Controller metode su samo 1-liner pozivi servisa.

---

## Ključne konvencije

### Kod

- **Nema novih komentara** osim za neočigledne workarounds ili skrivene invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
- Fuzzy matching threshold: `min_similarity = 0.92` (ne spuštati bez eksplicitnog razloga)
- SQL: isključivo parametrizovani upiti — nikad f-string u SQL-u

### Parseri (importers/)

- Svaki importer mora imati `exporter` i `importer` polja u `ImportResult`
- XML lookup se radi po paru `(exporter, tariff_code)` — ne samo po tariff_code
- CBBH kurs se čita iz baze, ne hardkoduje

### XML template (xml_template_service.py)

- Rb.48 (`odgodjeno_placanje`) se **ne prepisuje** iz historijskog XML-a — šifra se mijenja godišnje
- Mijenjati samo `TEMPLATE_FIELDS` whitelist — ne pisati ad-hoc logiku po polju

### Naimenovanja

- Rb.31 auto-opis se generiše po tarifi, ne prepisuje iz fakture
- `le_r31_trg_naziv` prikazuje komercijalne nazive za pregled, ali ASYCUDA XML Rub.31 mora ostati max 280 znakova / 3 linije; skraćivanje raditi pri buildanju XML-a

---

## Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| Direktni `import` iz `gui/tabs/agent/agent_controller.py` u servis | Kružni import |
| Mijenjati `TEMPLATE_FIELDS` van `xml_template_service.py` | Single source of truth |
| Hardkodovati IP adresu servera u kodu | Mora biti u `config.ini` |
| Dodavati UI logiku u servisne klase | Narušava razdvajanje slojeva |
| Brisati stub fajlove u `services/agent/` bez provjere importa | Backward compat |

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
| **Prihvatljiv ishod (scope lock)** | šta MORA ostati identično (npr. "validacija ostaje ista osim novog izvora dokaza", "GUI ne mijenja ponašanje osim prikaza") |
| **Nivo dozvole** | draft change only / no auto-merge / mandatory review / test gate required |

Ovo dopunjuje pravilo "MUST warn the user if impact analysis returns HIGH or
CRITICAL risk" (GitNexus sekcija ispod) — daje konkretan format umjesto generičkog
upozorenja i tjera agenta da prije izmjene eksplicitno zapiše granice zadatka.

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
- [ ] Testovi prolaze: `cd /home/radovan/Desktop/deklarant_pro && python -m pytest tests/ -q`
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

This project is indexed by GitNexus as **deklarant_pro** (38734 symbols, 60830 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
