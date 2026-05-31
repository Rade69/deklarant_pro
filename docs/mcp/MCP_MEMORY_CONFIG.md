# 🧠 MCP Universal Memory - Konfiguracija za Sve Agente

**Datum:** 2026-03-22  
**Projekt:** Deklarant Pro  
**Status:** ✅ Aktivno

---

## 📍 Lokacije Konfiguracija po Agentima

| Agent | Konfiguracijski Fajlovi | Status |
|-------|------------------------|--------|
| **Qwen** | `.qwen/settings.json`, `.qwen/mcp.json` | ✅ Konfigurisano |
| **Claude** | `CLAUDE.md`, `.claude/settings.local.json` | ✅ Konfigurisano |
| **Cline** | `.clinerules` | ✅ Konfigurisano |
| **Continue** | `.continuerc.json`, `.continue/config.ts`, `.continue/config.yaml` | ✅ Konfigurisano |
| **Qodo Ask** | `~/.qodo/agents/0dd25eb0-4f31-453d-a68a-d08f13ac50c0.toml` | ✅ Konfigurisano |
| **Qodo Plan** | `~/.qodo/agents/4d36c23b-a000-48f1-a069-40c1005c868f.toml` | ✅ Konfigurisano |
| **VSCode Kiro** | `.vscode/settings.json` | ✅ Konfigurisano |

---

## 🔌 MCP Server Konfiguracija

```json
{
  "mcpServers": {
    "universal-memory": {
      "command": "/home/radovan/Desktop/deklarant_pro/.venv/bin/python3",
      "args": ["/home/radovan/.agent_memory_system/memory_mcp_server_universal.py"],
      "env": {
        "PYTHONPATH": "/home/radovan/.agent_memory_system"
      }
    }
  }
}
```

---

## 🎯 Obavezne Instrukcije za Sve Agente

### NA POČETKU SVAKE SESIJE:

1. **Pozovi `get_project_overview`**
   ```
   project: "deklarant_pro"
   ```
   - Vraća: ukupan broj memory cells, scene, tipove
   - Daje kontekst o cijelom projektu

2. **Zatim koristi `query_memory`** za specifične teme:
   ```
   project: "deklarant_pro"
   query: "[tema o kojoj korisnik pita]"
   ```

---

## 📦 Šta Memorija Sadrži (13 Cells)

### Scene:
- **architecture** (9 cells) - Tab pattern, refactor status, config, import system
- **bugs** (1 cell) - NaimenovanjaTab recursion issue
- **testing** (1 cell) - Test coverage summary  
- **performance** (1 cell) - Code reduction metrics
- **decision** (1 cell) - Safe refactoring decisions

### Ključne Informacije:
| Tema | Detalji |
|------|---------|
| **Tab Refactor Pattern** | 3-layer: View/Controller/Service |
| **ZaglavljeTab** | ✅ 100% refaktorisan (2,545 → 2,527 linija) |
| **FakturaTab** | ✅ 100% refaktorisan (2,992 → 1,458 linija, -51.2%) |
| **NaimenovanjaTab** | ⚠️ Original vraćen (GUI recursion bug) |
| **SifarniciTab** | ✅ Service layer extracted (GUI netaknut) |
| **Ukupno** | 12,220 → 10,680 linija (-12.6%) |
| **Testovi** | 352 passed, 1 skipped |

---

## 🛠️ Dostupni MCP Tools

| Tool | Parametri | Opis |
|------|-----------|------|
| `get_project_overview` | `project: string` | Daje overview svih memorija projekta |
| `query_memory` | `project: string, query: string, limit: number` | Pretražuje memoriju po keywords |
| `list_projects` | - | Lista svih projekata u memoriji |
| `store_memory` | `project, scene, cell_type, content, salience` | Ručno dodavanje memorije |

---

## 📝 Primjeri Korištenja

### Primjer 1: Arhitektura
```
query_memory(
  project="deklarant_pro",
  query="Tab Refactor Pattern View Controller Service"
)
```

### Primjer 2: Status Refactor-a
```
query_memory(
  project="deklarant_pro", 
  query="FakturaTab ZaglavljeTab refactor status"
)
```

### Primjer 3: Bugovi i Lekcije
```
query_memory(
  project="deklarant_pro",
  query="bug recursion GUI safe approach"
)
```

### Primjer 4: Testovi
```
query_memory(
  project="deklarant_pro",
  query="testovi coverage integration"
)
```

---

## ⚠️ Važne Napomene

1. **Memorija ima prednost** nad općim opisima u dokumentima
2. **Uvijek prvo checkaj memoriju** prije nego što odgovoriš
3. **Koristi kontekst iz memorije** za bolje razumijevanje projekta
4. **Ako MCP ne radi**, provjeri:
   - Da li `.venv` postoji
   - Da li je `mcp` package instaliran (`pip list | grep mcp`)
   - Da li `memory_mcp_server_universal.py` postoji

---

## 🔧 Troubleshooting

### MCP Server Ne Radi
```bash
# Provjeri da li je mcp instaliran u .venv
.venv/bin/pip list | grep mcp

# Treba biti: mcp 1.26.0

# Provjeri da li server fajl postoji
ls -la ~/.agent_memory_system/memory_mcp_server_universal.py

# Testiraj CLI (treba API key za neke komande)
.venv/bin/python ~/.agent_memory_system/cli.py stats --project deklarant_pro
```

### Memorija Prazna
```bash
# Provjeri database
ls -la ~/.agent_memory_system/databases/

# Treba postojati: deklarant_pro.db (40KB)

# Provjeri sadržaj
sqlite3 ~/.agent_memory_system/databases/deklarant_pro.db "SELECT COUNT(*) FROM mem_cells;"
# Treba biti: 13
```

---

## 📊 Health Check Komande

```bash
# 1. MCP Package
.venv/bin/pip show mcp

# 2. MCP Server Fajl
ls -la ~/.agent_memory_system/memory_mcp_server_universal.py

# 3. Database
sqlite3 ~/.agent_memory_system/databases/deklarant_pro.db ".tables"

# 4. Memory Cells Count
sqlite3 ~/.agent_memory_system/databases/deklarant_pro.db "SELECT COUNT(*) FROM mem_cells;"

# 5. Projekat Overview (kroz MCP)
# Koristi MCP tool: get_project_overview(project="deklarant_pro")
```

---

*Kreirao: Qwen | 2026-03-22 | MCP Memory Integracija za Sve Agente*
