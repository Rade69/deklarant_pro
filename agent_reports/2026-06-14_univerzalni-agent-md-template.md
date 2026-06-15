# Univerzalni CLAUDE.md/AGENTS.md template za nove projekte

## Datum

2026-06-14

## Agent

Claude Sonnet 4.6 (Claude Code)

## Scope

- Novi folder `templates/agent-md/` sa dva nova fajla:
  `templates/agent-md/CLAUDE.md`, `templates/agent-md/AGENTS.md`
- Nije mijenjan postojeći root `CLAUDE.md`/`AGENTS.md` niti bilo koji kod

## Status izvora

- Root `CLAUDE.md` (uklj. dopunu iz commit-a `03f78f1`/`9bdb736`) i root
  `AGENTS.md` (sekcija "Handoff visokog rizika", "Format outputa", "Provjera
  prije predaje", DOC Guard, GitNexus footer) — status: aktivan, korišćeni
  kao IZVORNI MATERIJAL za genericizaciju (kopirano + zamijenjeno
  deklarant_pro-specifično sa `<<< POPUNI: ... >>>` placeholderima)

## Impact analiza

`gitnexus_detect_changes(scope="unstaged")`: `risk_level: "low"`,
`affected_count: 0`, `affected_processes: []`. Nova fascikla `templates/`
sadrži samo dokumentaciju (markdown) — bez ikakvog koda; novi fajlovi su
untracked pa se ne pojavljuju u `changed_symbols` (samo pre-postojeće
unstaged izmjene u `AGENTS.md`/`CLAUDE.md`/`naimenovanja_view.py` koje NISU
dio ovog zadatka).

## Šta je urađeno

Kreiran `templates/agent-md/` sa dva template fajla:

- **`CLAUDE.md`** — generička verzija root `CLAUDE.md`: sekcije "⚠️ JEZIK I
  PISMO" (primarni jezički direktiv), "Čitanje memorije na početku sesije"
  (opisuje fajl-baziranu memoriju `~/.claude/projects/<slug>/memory/`),
  "Projektne konvencije" (placeholder + uputstvo ŠTA/ZAŠTO/GDJE), "Stil
  koda", "Struktura projekta", "Testiranje", "Git konvencije", "Format
  zadatka za agenta", "Plan prije izmjene — HIGH/CRITICAL impact"
  (genericizovano: "alat za impact-analizu (npr. gitnexus_impact) ili
  ekvivalent"), "OBAVEZNA PROCEDURA" (Korak 1-5, Korak 5 sada opcionalan),
  "DOC Guard" (opcionalno), "Code Intelligence" (opcionalno, GitNexus kao
  primjer).
- **`AGENTS.md`** — generička verzija root `AGENTS.md`: "Kontekst projekta"
  (opcionalno, placeholder za `docs/CONTEXT.md`-stil fajl), "Obavezno prije
  kodiranja", "Jezik", "Tech stack" (placeholder tabela), "Arhitektura"
  (placeholder stablo + pattern napomena), "Ključne konvencije"
  (placeholder sekcije po modulu), "Zabrane specifične za ovaj projekat"
  (placeholder tabela), "Handoff visokog rizika" (genericizovano),
  "Format outputa", "Provjera prije predaje" (placeholder checklist + test
  komanda), "DOC Guard" i "Code Intelligence" (oba opcionalna).

Svaki placeholder ima oblik `<<< POPUNI: ... >>>` ili `<<< POPUNI/UKLONI:
... >>>` (za opcione sekcije koje projekat možda ne treba).

## Zašto je urađeno

Korisnik je tražio da se na osnovu deklarant_pro `CLAUDE.md`/`AGENTS.md`
napravi univerzalna osnova koja se može kopirati u korijen NOVOG projekta i
naknadno popuniti projektno-specifičnim podacima — da se ne kreće "od
nule" sa pravilima (jezik, git konvencije, memory protokol, agent_report
procedura, handoff visokog rizika) koja su se pokazala korisna u ovom
projektu.

Korisnik je izabrao: (1) DVA fajla (CLAUDE.md + AGENTS.md, kao original — ne
jedan kombinovani), (2) GitNexus/Code-Intelligence sekcije OSTAJU, ali kao
opcione sa napomenom "ukloni ako projekat ne koristi".

## Kako je urađeno

- Root `CLAUDE.md` (263 linije) i `AGENTS.md` (222 linije) pročitani u
  cjelosti (iz prethodne sesije, već u kontekstu).
- Sekcije podijeljene u dvije grupe:
  - **Opšta pravila** (zadržana skoro identično, samo blago genericizovana
    formulacija): jezički direktiv (kao prazan slot za odluku, ne
    pretpostavka da je srpski), memory protokol (opisan kroz STVARNI
    fajl-bazirani mehanizam dokumentovan u Claude Code "auto memory"
    sistemu — original CLAUDE.md referiše MCP alate
    `get_project_context`/`search_project_memory` koji nisu dio ovog
    template-a, ostavljen placeholder za taj slučaj), "Format zadatka",
    "OBAVEZNA PROCEDURA" (Korak 1-5), "Handoff visokog rizika", "Format
    outputa", "Plan prije izmjene".
  - **Projektno-specifične sekcije** (zamijenjene placeholderima sa
    uputstvom šta i KAKO popuniti, uz primjere iz deklarant_pro kao
    ilustraciju kategorija): "Projektne konvencije" (6 podtačaka →
    generička uputstva sa primjerima kategorija), "Stil koda" (emoji/jezik
    detalji), "Struktura projekta" (stablo direktorija), "Tech stack"
    tabela, "Arhitektura" (stablo + pattern), "Ključne konvencije" po
    modulu, "Zabrane" tabela.
- GitNexus/"Code Intelligence" sekcije (auto-generisani footer + "Plan
  prije izmjene" referenca + Korak 5) markirane kao OPCIONALNE sa
  `<<< POPUNI/UKLONI: ... >>>` i uputstvom da se inicijalna analiza pokrene
  (`npx gitnexus analyze`/`init`) da se footer generiše, ili da se sekcija
  potpuno ukloni ako projekat ne koristi takav alat.
- Dodata napomena na vrhu oba fajla: rade u paru, ali ako projekat koristi
  samo Claude Code mogu se spojiti u jedan `CLAUDE.md`.

## Šta nije dirano

- Root `CLAUDE.md`/`AGENTS.md` — nepromijenjeni (template je KOPIJA-derivat,
  ne izmjena originala).
- Pre-postojeće necommitovane izmjene: `AGENTS.md`/`CLAUDE.md` (GitNexus
  stat-bump nakon `npx gitnexus analyze`), `gui/tabs/naimenovanja_view.py` +
  `dist_client/gui/tabs/naimenovanja_view.py`,
  `services/declaration_draft_service.py` +
  `dist_client/services/declaration_draft_service.py` +
  `tests/unit/test_declaration_draft_service.py`, `client.log.lck` — sve
  nepovezano sa ovim zadatkom, ostavljeno netaknuto.
- Nikakav `.py`/kod fajl nije mijenjan — čisto novi dokumentacioni template.

## Verifikacija

- `gitnexus_detect_changes(scope="unstaged")`: `risk_level: "low"`,
  `affected_count: 0`, `affected_processes: []`.
- `git status --porcelain`: potvrđuje da je `templates/` jedini NOVI,
  netracked entitet relevantan za ovaj zadatak.
- Ručni pregled oba template fajla nakon pisanja — provjereno da svaka
  projektno-specifična referenca (PySide6, faktura tabovi, tarifni brojevi,
  deklarant_sistem.db, GitNexus brojke 41341/63866...) ima
  `<<< POPUNI ... >>>` zamjenu ili je premještena u "opciono" sekciju.

## Pronađeni problemi

Nema. Napomena (ne problem, nego svjesna odluka): original CLAUDE.md
referiše MCP memory alate (`get_project_context`/`search_project_memory`)
koji NISU dio aktivnog Claude Code "auto memory" mehanizma korišćenog u ovoj
sesiji (fajl-baziran, `~/.claude/projects/<slug>/memory/MEMORY.md`) — template
opisuje STVARNI fajl-bazirani mehanizam kao primarni, s placeholderom za
slučaj da novi projekat dodatno postavi MCP memory server.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
|------|--------|
| `d0738ee` | `docs(template): dodaj univerzalni CLAUDE.md/AGENTS.md template za nove projekte` |

## Rizici / ograničenja

- Čisto dokumentacioni template — nema funkcionalnog rizika.
- Template NIJE automatski sinhronizovan sa root `CLAUDE.md`/`AGENTS.md` —
  ako se pravila u root fajlovima dalje mijenjaju (npr. buduće dopune
  procedura), template treba RUČNO ažurirati ako se želi da odražava
  najnovije konvencije.
- GitNexus footer u template-u je potpuno placeholder — korisnik mora ručno
  pokrenuti `npx gitnexus analyze`/`init` u novom projektu da generiše
  stvarnu sekciju (ili je ukloniti).

## Potreban follow-up

- Nema obavezujućeg — template je samostalan, čeka kopiranje u budući
  projekat.
- Ako korisnik kasnije promijeni mišljenje o "2 fajla vs 1 kombinovani" ili
  GitNexus opciji, template treba ručno prilagoditi (nije generisan
  skriptom, pa nema "regenerate" komande).

## Potrebna korisnička potvrda

- Pregledati `templates/agent-md/CLAUDE.md` i `templates/agent-md/AGENTS.md`
  i potvrditi da su placeholderi na pravim mjestima i da nije izgubljeno
  nešto vrijedno iz originala.
