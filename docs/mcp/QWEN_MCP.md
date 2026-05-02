# 🤖 MCP Memory Integracija - Svi Agenti

**Konfiguracija za direktno čitanje memorije u svim AI agentima**

*Zadnje ažuriranje: 2026-03-22*

---

## ✅ Konfigurisani Agenti

| Agent | Konfiguracija | Lokacija | Status |
|-------|--------------|----------|--------|
| **Qwen** | `.qwen/settings.json` + `.qwen/mcp.json` | Project root | ✅ |
| **Claude** | `CLAUDE.md` (instructions) | Project root | ✅ |
| **Cline** | `.clinerules` | Project root | ✅ |
| **Continue** | `.continuerc.json` + `.continue/config.ts` | Project root | ✅ |
| **Qodo Ask** | `~/.qodo/agents/*.toml` | Global config | ✅ |
| **Qodo Plan** | `~/.qodo/agents/*.toml` | Global config | ✅ |
| **VSCode Kiro** | `.vscode/settings.json` | Project root | ✅ |

---

## 🎨 Terminal Font (Nerd Font)

**Instaliran:** JetBrainsMono Nerd Font 11  
**Dokumentacija:** `docs/NERD_FONT_INSTALL.md`

Za pravilno prikazivanje ikonica u terminalu:
```bash
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrainsMono Nerd Font 11'
```

---

## 🎯 Zajedničke Instrukcije za Sve Agente

### NA POČETKU SVAKE SESIJE (OBAVEZNO):

1. **Učitaj MCP Memory Server konfiguraciju**
   - Lokacija: `.qwen/mcp.json` ili `.qwen/settings.json`
   - Server: `universal-memory`

2. **Pozovi `get_project_overview`**
   ```
   project: "deklarant_pro"
   ```
   - Daje pregled: 13 cells, 4 scene (architecture, bugs, testing, performance)

3. **Koristi `query_memory` za specifične teme**
   ```
   project: "deklarant_pro"
   query: "[tema koju korisnik pita]"
   ```

---

## 📦 Šta Memorija Sadrži

**13 memory cells** u 4 scene:

| Scene | Broj Cells | Sadrži |
|-------|------------|--------|
| `architecture` | 9 | Tab pattern, refactor status, config, import system |
| `bugs` | 1 | NaimenovanjaTab recursion issue |
| `testing` | 1 | Test coverage (352 passed) |
| `performance` | 1 | Code reduction metrike (-12.6%) |
| `decision` | 1 | Safe refactoring decisions |

---

## 📝 Dokumentacija

- **MCP_MEMORY_CONFIG.md** - Potpuna MCP konfiguracija i primjeri
- **QWEN.md** - Kontekst iz prethodnih sesija (flat file memorija)
- **CLAUDE.md** - Claude-specifične instrukcije

---

## 🔧 Troubleshooting

```bash
# Provjeri MCP package
.venv/bin/pip list | grep mcp  # Treba: mcp 1.26.0

# Provjeri database
ls -la ~/.agent_memory_system/databases/deklarant_pro.db

# Provjeri broj cells
sqlite3 ~/.agent_memory_system/databases/deklarant_pro.db "SELECT COUNT(*) FROM mem_cells;"
# Treba: 13
```

---

*Kreirao: Qwen | 2026-03-22*
