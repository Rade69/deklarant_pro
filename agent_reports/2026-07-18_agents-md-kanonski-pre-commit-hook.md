# Agent report — AGENTS.md kanonski fajl + git pre-commit hook

## Datum
2026-07-18

## Agent
Claude Code (Fable 5)

## Scope
`AGENTS.md`, `CLAUDE.md`, `docs/CONTEXT.md`, `scripts/git-hooks/pre-commit`,
`.gitattributes`, lokalna git konfiguracija (`core.hooksPath`).

## Status izvora
- `AGENTS.md` (stari) — aktivan, korišćen kao osnova; sadržao je dijelove kojih
  nije bilo u CLAUDE.md (zabrane, handoff format, tech stack)
- `CLAUDE.md` (stari) — aktivan, sav univerzalni sadržaj prenešen u AGENTS.md
- `dist_client/AGENTS.md`, `dist_client/CLAUDE.md`, `docs/AGENTS.md`,
  `templates/agent-md/*` — **zastarjele kopije/šabloni, namjerno NISU dirani**

## GitNexus impact
`gitnexus_detect_changes(scope=all)` prije commita: **risk low**, 0 pogođenih
execution flow-ova, 5 izmijenjenih fajlova (samo dokumentacija + hook, bez koda).
Napomena: alat je prijavio "touched" sekcije i u fajlovima koji nisu mijenjani
(dist_client/, templates/) — indeks je bio zastario (dde050a), mapiranje po
sličnosti sekcija. Stvarno izmijenjeni fajlovi provjereni kroz `git status`.

## Šta je urađeno
1. `AGENTS.md` postao **kanonski fajl** pravila za sve agente — spojen sav
   univerzalni sadržaj iz CLAUDE.md (projektne konvencije, format zadatka,
   plan prije izmjene, obavezna procedura Korak 1-5, testiranje, DOC Guard,
   GitNexus blok). Usput ispravke: pytest komanda bez hardkodovane Linux
   putanje, IP servera zamijenjen referencom na config.ini, dodane zabrane
   iz memorije (f-string QSS, tab_factory raise).
2. `CLAUDE.md` sveden na: `@AGENTS.md` import + jezička direktiva +
   Claude-specifična memorija (MCP protokol, fajl memorija).
3. `docs/CONTEXT.md` — nova sekcija 15 (multiagentski harness) + datum.
4. `scripts/git-hooks/pre-commit` — versionisan sh hook: py_compile na staged
   .py fajlovima (blokira commit na sintaksnu grešku) + podsjetnici za
   Korak 1-5. `git config core.hooksPath scripts/git-hooks` postavljen na
   ovoj (Windows) mašini.
5. `.gitattributes` — `scripts/git-hooks/* text eol=lf` (CRLF lomi sh na Fedori).

## Zašto je urađeno
Multiagentski radni tok (Claude Code, Codex, DeepSeek, GLM, Kimi, MiniMax):
CLAUDE.md i AGENTS.md su duplirali i driftovali sadržaj (GitNexus blok u oba,
procedura samo u CLAUDE.md koju ne-Claude agenti ne čitaju). Najbolja praksa
2026: jedan kanonski AGENTS.md (čita ga 30+ alata) + deterministička pravila
kao hooks umjesto prompt instrukcija. Alternativa (symlink CLAUDE.md→AGENTS.md)
odbačena jer bi izgubila Claude-specifični memorijski protokol.

## Kako je urađeno
Spajanje ručno sekciju po sekciju (ne konkatenacija) — pri konfliktu uzimana
novija/tačnija verzija (npr. Rub.31 280 znakova pravilo identično u oba).
Hook je POSIX sh bez emoji-ja (cp1252 lekcija iz memorije), radi kroz
`core.hooksPath` da bude versionisan i važi za sve agente i oba OS-a.

## Šta nije dirano
- `dist_client/AGENTS.md`, `dist_client/CLAUDE.md`, `dist_client/docs/*` —
  runtime kopije, sinhronizacija je poseban zadatak
- `docs/AGENTS.md`, `templates/agent-md/*` — stariji dokumenti/šabloni
- `.claude/settings.json` (doc-guard hook ostaje netaknut)
- `docs/agent-tasks/*`, postojeći `.git/hooks/` (samo sample fajlovi)

## Verifikacija
- Hook prolazna grana: `sh scripts/git-hooks/pre-commit` bez staged .py → OK poruka
- Hook blokirajuća grana: namjerno pokvaren `_hook_test_bad.py` staged →
  SyntaxError prikazan, EXIT=1, commit blokiran; test fajl uklonjen
- Hook u stvarnom toku: oba commita (6d08f15, d4a923b) prošla kroz hook
- Exec bit u indexu: `create mode 100755`

## Pronađeni problemi
- GitNexus `detect_changes` na zastarjelom indeksu prijavljuje sekcije
  nedirnutih fajlova kao "touched" — potencijalno lažno pozitivno za buduće
  agente; uvijek ukrstiti sa `git status`.
- `AGENTS.md` je navodio IP servera 192.168.0.69, memorija kaže da je dmserver
  DHCP (zadnje .54) — kontradikcija riješena uklanjanjem IP-a iz dokumenta
  (u skladu sa vlastitom zabranom hardkodovanja IP-a).

## Konflikti / kontradiktorni izvori
- Stari CLAUDE.md: `Co-Authored-By: Claude Sonnet 4.6` fiksno vs. multiagentski
  tok — u AGENTS.md sada generički "ime modela koji je radio". Potvrda: NE
  (kozmetika).
- IP servera (vidi iznad). Potvrda: NE (dokument sada upućuje na config.ini).

## Commitovi
| Hash | Poruka |
| --- | --- |
| 6d08f15 | docs(agenti): AGENTS.md postaje kanonski fajl za sve agente |
| d4a923b | chore(hooks): git pre-commit hook - py_compile + podsjetnici Korak 1-5 |

## Rizici / ograničenja
- `core.hooksPath` je **lokalna** git konfiguracija — na Fedora dev mašini
  (.131) mora se jednom ručno pokrenuti `git config core.hooksPath scripts/git-hooks`
- Hook provjerava radnu verziju fajla, ne staged sadržaj (partial staging
  teoretski može proći) — prihvatljiv kompromis za jednostavnost
- py_compile na ovoj mašini koristi Python 3.14; projekat cilja 3.11+ —
  sintaksne razlike malo vjerovatne
- Agenti koji ne čitaju AGENTS.md konvenciju i dalje mogu ignorisati proceduru;
  hook pokriva samo commit tačku

## Potreban follow-up
- Fedora mašina: postaviti `core.hooksPath` (jedna komanda)
- Odlučiti da li sinhronizovati/obrisati zastarjele kopije
  (`dist_client/AGENTS.md`, `docs/AGENTS.md`) — kandidati za brisanje
- Preostale tačke iz preporuka: worktree po agentu, pytest gate, cross-review

## Potrebna korisnička potvrda
- Da li zastarjele kopije u `dist_client/` i `docs/` treba obrisati ili
  sinhronizovati (nisu dirane u ovom zadatku)
- Na Fedori pokrenuti instalacionu komandu hooka pri sljedećem radu tamo
