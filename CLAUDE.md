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
