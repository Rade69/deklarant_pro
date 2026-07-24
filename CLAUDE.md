# CLAUDE.md — Deklarant Pro

**Sva projektna pravila su u kanonskom fajlu koji čitaju SVI agenti:**

@AGENTS.md

Pravila se mijenjaju ISKLJUČIVO u `AGENTS.md` — ovaj fajl sadrži samo
Claude-specifične dodatke ispod. Ne duplirati sadržaj između fajlova.

---

## ⚠️ JEZIK: ISKLJUČIVO SRPSKI LATINICA

Svi odgovori, objašnjenja i commit poruke na srpskom, latinica.
Nikada ćirilica, nikada engleski (osim na eksplicitan zahtjev).

---

## Claude memorija (samo Claude Code)

### MCP memorija — na početku SVAKE sesije

1. `get_project_context(project_id="deklarant_pro")`
2. `search_project_memory(project_id="deklarant_pro", query="arhitektura tabovi refactor status")`
3. Dodatni query prema zadatku:
   - Refactoring → `"faktura zaglavlje service controller"`
   - Bugovi → `"bugovi rješenja known issues"`
   - GUI → `"GUI PySide6 tabovi layout"`
   - Testovi → `"testovi coverage"`

MCP memorija ima prvenstvo nad dokumentacijom. Čitati SAMO memoriju vezanu
za projekat `deklarant_pro`.

### Fajl memorija

Sesijska memorija je u `~/.claude/projects/<projekat>/memory/`
(format: `YYYY-MM-DD_kratki-opis.md` sa YAML frontmatterom + `MEMORY.md` index).
Nakon zadatka: ne-očigledne stvari upisati i tu I u `docs/CONTEXT.md`
(zajednička memorija za sve agente — vidi AGENTS.md, Korak 2).

---

## Napomena o proceduri

Obavezna procedura nakon zadatka (Korak 1-5), format zadatka, plan prije
izmjene za HIGH/CRITICAL impact, DOC Guard i GitNexus pravila — sve je u
`AGENTS.md`. Git pre-commit hook (`scripts/git-hooks/pre-commit`) sprovodi
py_compile provjeru — ne koristiti `--no-verify`.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deklarant_pro** (46572 symbols, 71912 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
