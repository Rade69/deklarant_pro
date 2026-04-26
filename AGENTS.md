# AGENTS.md â€” Deklarant Pro projektni standardi

Ovaj fajl Äitaju svi agenti koji rade na ovom projektu: Qwen Code, GitHub Copilot, Cursor,
MiniMax, CLI agenti i drugi. Dopunjuje globalni `~/.claude/AGENTS.md` â€” ne zamjenjuje ga.

---

## Kontekst projekta â€” proÄitaj prije kodiranja

**OBAVEZNO: ProÄitaj `docs/CONTEXT.md` prije bilo kakvog kodiranja.**

Taj fajl sadrÅ¾i ne-trivijalne odluke, zabranjene patterne i poznate bugove
koji nisu vidljivi iz samog koda. Dostupan je svim agentima jer je u git repozitoriju.

```text
docs/CONTEXT.md   â† zajedniÄka memorija za sve agente (Claude, Qwen, DeepSeek...)
```

Klauza `CLAUDE.md` u korijenu projekta sadrÅ¾i formatske konvencije i projektne standarde.
ProÄitaj je ako radiÅ¡ Å¡ire izmjene ili nisi siguran u konvencije.

> **Samo za Claude:** Detaljne sesijske biljeÅ¡ke nalaze se i u
> `~/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/`
> ali `docs/CONTEXT.md` je autoritativni izvor za sve agente.

---

## Obavezno prije nego poÄneÅ¡ kodirati

NapiÅ¡i kratko (2-4 reÄenice) Å¡ta si razumio iz zadatka i Å¡ta planiraÅ¡ uraditi.
ÄŒekaj potvrdu korisnika prije implementacije ako zadatak nije jednoznaÄan.

---

## Jezik

- Svi odgovori korisniku: **srpski, latinica**
- Komentari u kodu: engleski (prati stil koji fajl veÄ‡ koristi)
- Nikada Ä‡irilica â€” nigdje, ni u komentarima ni u stringovima koji se prikazuju
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
â”œâ”€â”€ core/draft/          # Draft modeli: DeclarationDraft, InvoiceLine, NaimenovanjeDraft
â”œâ”€â”€ gui/tabs/            # GUI tabovi (agent_tab, faktura_tab, naimenovanja_tab...)
â”‚   â””â”€â”€ agent/
â”‚       â”œâ”€â”€ agent_controller.py      # Tanak controller â€” samo 1-liner wrapper metode
â”‚       â””â”€â”€ services/                # Sva logika izvuÄena ovdje
â”‚           â”œâ”€â”€ xml_workflow_service.py
â”‚           â”œâ”€â”€ import_pipeline_service.py
â”‚           â””â”€â”€ chat_intent_handler.py
â”œâ”€â”€ importers/           # PDF/Excel parseri po dobavljaÄu
â”œâ”€â”€ services/            # Business logika
â”‚   â””â”€â”€ agent/
â”‚       â”œâ”€â”€ chat/        # intent_classifier, chat_memory, namjere
â”‚       â”œâ”€â”€ tariff/      # hybrid_tariff_agent, rag, matching
â”‚       â”œâ”€â”€ learning/    # historical_learning, exporter_xml_indexer
â”‚       â””â”€â”€ validation/  # declaration_validator, xml_template_service
â”œâ”€â”€ database/            # SQLite: deklarant_sistem.db, zvanicna_tarifa.db
â””â”€â”€ ui/                  # Qt .ui fajlovi
```

**Pattern za services/agent/:** slobodne funkcije koje primaju `ctrl` kao prvi argument,
servisna klasa ih omotava kao public API. Controller metode su samo 1-liner pozivi servisa.

---

## KljuÄne konvencije

### Kod

- **Nema novih komentara** osim za neoÄigledne workarounds ili skrivene invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
- Fuzzy matching threshold: `min_similarity = 0.92` (ne spuÅ¡tati bez eksplicitnog razloga)
- SQL: iskljuÄivo parametrizovani upiti â€” nikad f-string u SQL-u

### Parseri (importers/)

- Svaki importer mora imati `exporter` i `importer` polja u `ImportResult`
- XML lookup se radi po paru `(exporter, tariff_code)` â€” ne samo po tariff_code
- CBBH kurs se Äita iz baze, ne hardkoduje

### XML template (xml_template_service.py)

- Rb.48 (`odgodjeno_placanje`) se **ne prepisuje** iz historijskog XML-a â€” Å¡ifra se mijenja godiÅ¡nje
- Mijenjati samo `TEMPLATE_FIELDS` whitelist â€” ne pisati ad-hoc logiku po polju

### Naimenovanja

- Rb.31 auto-opis se generiÅ¡e po tarifi, ne prepisuje iz fakture
- `le_r31_trg_naziv` prikazuje komercijalne nazive za pregled, ali ASYCUDA XML Rub.31 mora ostati max 280 znakova / 3 linije; skraÄ‡ivanje raditi pri buildanju XML-a

---

## Zabrane specifiÄne za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| Direktni `import` iz `gui/tabs/agent/agent_controller.py` u servis | KruÅ¾ni import |
| Mijenjati `TEMPLATE_FIELDS` van `xml_template_service.py` | Single source of truth |
| Hardkodovati IP adresu servera u kodu | Mora biti u `config.ini` |
| Dodavati UI logiku u servisne klase | NaruÅ¡ava razdvajanje slojeva |
| Brisati stub fajlove u `services/agent/` bez provjere importa | Backward compat |

---

## Format outputa

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
Å TA JE URAÄENO: kratko
Å TA NIJE URAÄENO: (ako PARCIJALNO/BLOKIRANO)
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

