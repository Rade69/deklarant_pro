# Audit — Hooks / Memory / Docs sistem

**Datum:** 2026-05-11  
**Autor:** Claude Sonnet 4.6 (automated audit)  
**Obuhvat:** Hook konfiguracije, MCP memory server, dokumentacija, decision records, `# DOC:` linkovi u kodu

---

## 1. Hook konfiguracije

### Global hooks (`~/.claude/settings.json`)

Dva aktivna hooka na globalnom nivou:

| Event | Šta radi | Timeout |
|---|---|---|
| **PreToolUse** | Za Grep/Glob/Bash pretrage ubacuje GitNexus semantic kontekst (`gitnexus augment CLI`) | 7000ms |
| **PostToolUse** | Detektuje git mutacije (commit/merge/rebase/pull) i notificira agenta da reindeksira GitNexus ako je indeks zastario | 3000ms |

**Implementacija:** `~/.claude/hooks/gitnexus/gitnexus-hook.cjs` (269 linija Node.js, CJS moduli)  
Fallback: koristi `npx gitnexus` ako lokalni install nije dostupan.

### Project-level hooks

Ne postoje. Direktorij `.claude/hooks/` u projektu nije kreiran, nema project-specifičnih hookova u `.claude/settings.json`.

---

## 2. MCP Memory server

**Konfiguracija** (u `~/.claude/settings.json`, sekcija `mcpServers`):

```json
"project-memory": {
  "command": "/usr/bin/python3",
  "args": ["/home/radovan/.mcp_memory_system/run_server.py"],
  "env": { "PYTHONPATH": "/home/radovan/.mcp_memory_system" }
}
```

**Lokacija:** `~/.mcp_memory_system/`  
**Tip:** `MultiTenantMemoryServer` — podržava više projekata iz jedne instance  
**Struktura:** `run_server.py`, `src/mcp/`, `databases/`, `docs/`, `scripts/`, `logs/`

### Relevantni Python fajlovi u projektu

| Fajl | Napomena |
|---|---|
| `mcp_server/server.py` | MCP server za deklarant_pro |
| `services/agent/mcp_facade.py` | Fasada prema MCP toolovima |
| `services/agent/chat_memory_service.py` | Chat memory servis |
| `services/agent/chat/chat_memory_service.py` | Duplikat / refaktored verzija |
| `memory/memory_mcp_server_universal.py` | Universal MCP server |
| `memory/memory_system.py` | Core memory sistem |
| `memory/seed_deklarant_memory.py` | Seedovanje projektne memorije |
| `memory/test_refactoring_memory.py` | Testovi |
| `memory/update_refactoring_memory.py` | Update skripte |
| `memory/check_memory_report.py` | Reporting |

---

## 3. Dokumentacija i decision records

### Markdown fajlovi po lokacijama

| Lokacija | Broj .md fajlova | Napomena |
|---|---|---|
| `docs/` (rekurzivno) | ~88 | Decisions, architecture, sections, agent-tasks, itd. |
| `agent_reports/` | 7 | Izvještaji od 3–9. maja 2026 |
| korijen projekta | 6 | CLAUDE.md, AGENTS.md, AGENT_CODE_DOC.md, AGENT_IMPROVEMENT_PLAN.md, QWEN.md, README.md |

### Decision records (`docs/decisions/`)

| Fajl | Tema |
|---|---|
| `001-tool-use-refactoring.md` | Refaktoring tool-use arhitekture |
| `002-tool-dispatcher-integration.md` | Integracija tool dispatchera |
| `003-multi-spedicija-prilagodba.md` | Prilagodba za multi-špediciju |
| `004-implementacioni-plan-multi-spedicija.md` | Implementacioni plan |

### Ostali architecture dokumenti

- `docs/architecture/STYLE_GOVERNANCE.md` — stilske konvencije
- `docs/architecture/STYLE_INVENTORY.md` — inventar stilova
- `docs/architecture/INLINE_STYLE_AUDIT.md` — audit inline stilova
- `docs/agent-tasks/style-refactor/TASK-001-style-inventory.md`
- `docs/agent-tasks/style-refactor/TASK-003-inline-styles-audit.md`

### Agent reports (`agent_reports/`)

| Fajl | Sadržaj |
|---|---|
| `2026-05-03_style-refactor-task-001-003-005.md` | Style Refactor TASK-001, 003, 005 |
| `2026-05-03_style-refactor-task-002-004.md` | Style Refactor TASK-002, 004 |
| `2026-05-09_rub36-rub44-blagic-loren-fix.md` | Rub.36/Rub.44 fix (Blagić Loren) |
| `2026-05-09_sql-fstring-fix.md` | SQL f-string sigurnosna ispravka |
| `2026-05-09_produkcijska-ociscenja.md` | Produkcijska čišćenja (sigurnost, pool, lozinka) |
| `analiza-producione-spremnosti.md` | Dubinska analiza produkcijske spremnosti |
| `go-live-checklist.md` | Go-Live Checklist |

---

## 4. `# DOC:` linkovi u kodu

**Ukupno:** 32 pojavljivanja u 10 Python fajlova

Primjeri:

| Fajl | Linija | Cilj |
|---|---|---|
| `core/utils/form_validator.py` | 16 | `docs/sections/form-validator.md` |
| `importers/smart_pdf_importer.py` | 23 | `docs/sections/pdf_parse_pipeline.md` |
| `services/agent/mcp_facade.py` | 5 | `docs/sections/mcp-server-architecture.md` |
| `mcp_server/tools/tariff_history.py` | 4 | `docs/sections/mcp-tariff-history-tool.md` |
| `mcp_server/tools/product_origin.py` | 4, 34 | `docs/sections/mcp-product-origin-tool.md` |

---

## 5. MEMORY.md status

**Lokacija:** `~/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/MEMORY.md`  
**Veličina:** 499 linija ⚠️ (sistem limit: 200 linija — ostatak se ne učitava u kontekst)

**Sadržaj:** EUR.1/PE2 povlastice (april 2026), branding, style refactor (TASK-001–005), produkcijski cleanup (maj 2026), nove DB tabele, novi servisi.

---

## 6. Zbirna tablica

| Komponenta | Postoji | Lokacija | Napomena |
|---|---|---|---|
| Global hooks | **DA** | `~/.claude/settings.json` | PreToolUse + PostToolUse (GitNexus) |
| Hook skriptovi | **DA** | `~/.claude/hooks/gitnexus/gitnexus-hook.cjs` | 269 linija Node.js |
| Project hooks | **NE** | — | Nije konfigurisano |
| Decision records | **DA** | `docs/decisions/` | 4 ADR fajla (001–004) |
| `# DOC:` linkovi | **DA** | 10 Python fajlova | 32 pojavljivanja |
| MCP memory server | **DA** | `~/.mcp_memory_system/` | `project-memory`, multi-tenant |
| Agent reports | **DA** | `agent_reports/` | 7 izvještaja (maj 2026) |
| AGENTS.md | **DA** | korijen projekta | 51 linija, standardi za sve agente |
| MEMORY.md | **DA** ⚠️ | `~/.claude/projects/.../memory/` | 499 linija — **over limit** |
| Link checker skript | **NE** | — | Ne postoji — mogući broken `# DOC:` linkovi |

---

## 7. Preporuke (za informaciju)

1. **MEMORY.md** treba reorganizaciju — 499 linija od kojih se ~300 ne učitava u kontekst
2. **Link checker** — nema skripte koja verifikuje da `# DOC:` ciljevi postoje na disku; 32 linka su neprovjrena
3. **Project hooks** — razmotriti da li postoji potreba za project-specifičnim hookovima (npr. auto-run testova)
