# MCP Memory Server — Aktivacija i migracija

**Datum:** 2026-05-11  
**Status:** Završeno

## Šta je urađeno

1. Ispravni nazivi MCP alata u `CLAUDE.md` i `.claude/settings.json`
2. Kreiran `deklarant_pro` projekat u PostgreSQL `mcp_memory` bazi
3. Ispravljen bug u MCP serveru (`list_tools` vraćao dict umjesto `Tool` objekata)
4. Migrirano 28 flat `.md` memorijskih fajlova u PostgreSQL

## Kako je urađeno

### Problem 1 — Pogrešni nazivi alata
`CLAUDE.md` i `.claude/settings.json` referencirali `get_project_overview` i `query_memory` — alati koji ne postoje. Tačni nazivi su `get_project_context(project_id=...)` i `search_project_memory(project_id=...)`.

### Problem 2 — Pogrešna baza
MCP server koristi lokalnu PostgreSQL bazu `mcp_memory` (Unix socket `/var/run/postgresql`), ne SQLite fajl. Projekat `deklarant_pro` nije postojao u PostgreSQL — kreiran direktno putem `psql`.

### Problem 3 — MCP server bug (list_tools)
`list_tools` handler u `~/.mcp_memory_system/src/mcp/memory_mcp_server.py` vraćao listu plain Python dict-ova. MCP framework 1.26.0 poziva `tool.name` na svakom elementu (atribut, ne dict ključ) → `AttributeError: 'dict' object has no attribute 'name'`.

**Fix:** Dodati import `Tool` iz `mcp.types`, konvertovati svaki dict u `Tool(name=..., description=..., inputSchema=...)` prije returna.

### Migracija flat memorija
28 `.md` fajlova iz `~/.claude/projects/.../memory/` migrirano kao `memory_records` u PostgreSQL:
- Fajlovi sa YAML frontmatterom: `name`, `description`, `type` → `topic`, `summary`, `memory_type`
- Fajlovi sa H1 naslovom: naslov kao `name`, prvi paragraf kao `summary`
- Svi uneseni sa `status=approved`, `confidence=0.9`, `source_type=flat_memory_migration`

## Zašto

Cilj je bio da memorija bude dostupna svim agentima (Claude, Qwen, Cline, Codex) kroz jedan MCP protokol, a ne samo kroz flat fajlove koje čita Claude Code direktno.

## Commit tabela

| Hash | Opis |
|------|------|
| `5678df7` | fix(memory): ispravni nazivi MCP alata |
| `cbb083c` | chore: ažuriraj GitNexus statistike |

## Napomene

- MCP server je globalni (`~/.mcp_memory_system/`) — nije u git repozitoriju projekta
- Fix `list_tools` → `Tool` objekti je permanentna izmjena MCP servera
- Flat `.md` fajlovi ostaju netaknuti kao backup
- Qwen/Cline/Codex konfiguracija (Korak 4) ostaje za buduću sesiju
