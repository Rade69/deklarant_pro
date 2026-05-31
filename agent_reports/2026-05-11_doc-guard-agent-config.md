# DOC Guard — Ažuriranje agent konfiguracija

**Datum:** 2026-05-11  
**Agent:** Claude Sonnet 4.6  
**Zadatak:** Dodavanje DOC Guard pravila u sve agent konfiguracije

---

## Izmijenjeni fajlovi

| Fajl | Šta je dodano |
|---|---|
| `~/.codex/USTAV_AGENTA.md` | Sekcija 13 — kompletna DOC Guard pravila (13.1–13.5) |
| `AGENTS.md` | Kratki DOC Guard blok (BROKEN/STALE/ručna provjera) |
| `CLAUDE.md` | Kratki DOC Guard blok (isti format) |
| `QWEN.md` | Kratki DOC Guard blok + dodan `# QWEN.md` H1 heading |
| `AGENT_CODE_DOC.md` | Sekcija "Pravila za # DOC: putanje" (5 pravila) |

## Sadržaj sekcije 13 (USTAV_AGENTA.md)

- **13.1** — Šta je DOC Guard (hook injektuje reminder pri Write/Edit)
- **13.2** — BROKEN: obavezna STOP akcija, ne commitovati sa broken linkom
- **13.3** — STALE: procijeni logička vs kozmetička izmjena
- **13.4** — Kako pisati `# DOC:` (putanja, jedan po cjelini, bez specijalnih znakova)
- **13.5** — Ručna provjera: `bash scripts/doc_link_checker.sh .`

## Potvrda

```
AGENTS.md:137:## DOC Guard        ✅
CLAUDE.md:179:## DOC Guard        ✅
QWEN.md:3:## DOC Guard            ✅
AGENT_CODE_DOC.md:183: Pravila za # DOC: putanje  ✅
USTAV_AGENTA.md:312:## 13. DOC Guard — obavezna pravila  ✅
```
