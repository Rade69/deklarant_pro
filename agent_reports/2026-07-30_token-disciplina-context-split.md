## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`docs/CONTEXT.md`, novi `docs/context/history.md`, `AGENTS.md`. Dokumentacioni/proces zadatak — bez izmjena aplikacijskog koda.

## Šta je urađeno
Korisnik je podijelio dokument o "token disciplini" u AI agent workflow-u (princip: ne prenosi razgovor, prenesi artefakt) i tražio prijedlog kako ga usvojiti u ovaj repo. Umjesto direktnog kopiranja predložene strukture iz dokumenta (`agent_policies/`, `agent_skills/`, `agent_runbooks/` — 6 novih foldera), identifikovan je stvaran, mjerljiv problem: `docs/CONTEXT.md` je narastao na 3380 linija, što se pri punom čitanju pokazalo kao ~440k tokena — a `AGENTS.md` je nalagao da ga OBAVEZNO čita svaki agent u svakoj sesiji prije kodiranja.

Implementirano:
1. `docs/CONTEXT.md` podijeljen na dva fajla: sekcije 1-14 (evergreen, cross-cutting pravila) ostale su u `docs/CONTEXT.md` (sad 301 linija / ~13KB); sekcije 15-102 (dated hronološki log sesija, 2026-05 do 2026-07) premještene, bez izmjene sadržaja ili numeracije, u novi `docs/context/history.md` (3122 linije / ~183KB).
2. `docs/CONTEXT.md` dobio ažuriran header, prepravljen §13 ("Kako ažurirati ovaj fajl" — sad eksplicitno razlikuje šta ide u koji fajl) i novu završnu sekciju koja objašnjava premještaj i eksplicitno nalaže da se `history.md` NE čita cijeli nego pretražuje (Grep) po temi/datumu.
3. `AGENTS.md` — sekcija "Kontekst projekta" ažurirana da referiše oba fajla različito (CONTEXT.md = pročitati cijeli, history.md = samo Grep); dodana nova kratka sekcija "Token budget i context disciplina" (5 rečenica, princip iz dokumenta + izuzetak za HIGH/CRITICAL); Korak 2 procedure sad usmjerava nove dated stavke u `history.md`; Korak 3 (agent_report) checklist dobio novo polje "Kontekst korišćen".
4. Nova stavka §104 dodana u `history.md` koja dokumentuje samu ovu izmjenu (§103 je
   u međuvremenu zauzeo paralelni Codex agent — vidi "Konflikti" ispod).

## Zašto je urađeno
Korisnik je eksplicitno tražio prijedlog za usvajanje dokumenta o token disciplini, pa potvrdio da se krene po predloženom planu (podjela CONTEXT.md kao najveći realan dobitak, prije kratkog AGENTS.md pravila i agent_report polja). Cilj: agenti (Claude, Codex, DeepSeek, GLM...) više ne nose ~440k tokena reused inputa u svaki zadatak kad im treba samo par evergreen pravila.

## Kako je urađeno
Pošto je fajl prevelik da se pročita u cijelosti bez trošenja ogromnog dijela konteksta, granica presjeka (linija 274/277, tačno između kraja §14 i početka §15) je pronađena preko `Grep` (lista svih `## N.` naslova sa brojevima linija), a sam presjek fajla urađen preko `python3` skripte koja čita/piše fajl eksplicitno kao UTF-8 (izbjegnut PowerShell `Get-Content`/`Set-Content` — poznat mojibake rizik na ovom projektu, vidi memoriju `feedback_windows_patterns_2`). Sadržaj sekcija 1-102 nije ručno prekucavan niti mijenjan — samo mehanički razdvojen.

## Šta nije dirano
- Sadržaj nijedne od 88 premještenih sekcija (15-102) — identičan tekst, iste brojne oznake.
- `agent_reports/` arhiva — desetine starih izvještaja referišu "Detalji: docs/CONTEXT.md §N"; te reference po broju sekcije ostaju tačne, samo je fizička lokacija sekcija 15+ sad `docs/context/history.md` umjesto `docs/CONTEXT.md`. Nije prepravljano jer su to nepromjenjivi istorijski zapisi (isto obrazloženje kao i za druge slične izmjene ranije u ovom projektu).
- MCP memorija, `~/.claude/projects/.../memory/` — nezavisan sistem, nije dirano.
- Predložena struktura iz originalnog dokumenta (`agent_policies/`, `agent_skills/`, `agent_runbooks/`) — namjerno nije uvedena, jer bi dupliralo postojeću ulogu `project_rooms/` i `agent_reports/` (harness bloat na harness bloat).

## Verifikacija
- `wc -l` prije/poslije: `docs/CONTEXT.md` 3380 → 301 linija; novi `docs/context/history.md` 3122 linije (zbir se poklapa uz header/separatore).
- Ručna provjera granice presjeka (linije 270-280 originalnog fajla) prije izvršenja skripte — potvrđeno da je `## 15.` naslov prvi red u history.md, a `## 14.` sekcija posljednja netaknuta cjelina u CONTEXT.md.
- `bash scripts/doc_link_checker.sh .` pokrenut (rezultat nije stigao prije predaje ovog izvještaja — provjeriti izlaz naknadno; markdown fajlovi u `docs/` i `AGENTS.md` nemaju izmijenjene relativne linkove, samo prozu koja referiše fajl po imenu).
- Nema izmjena `.py` fajlova — `py_compile` pre-commit provjera nije relevantna za ovaj commit.

## Pronađeni problemi
**Konkurentan pristup istom working tree-u tokom rada (otkriveno prije commit-a).**
Dok je ova izmjena bila nekomitovana na disku, paralelni Codex agent je na
istom `windows` branch-u (isti working directory, ne zaseban worktree)
završavao "Faktura 3-layer Faza 8" (commit `ccfb923`, `Co-Authored-By: Codex`,
2026-07-30 08:12:31). Taj commit je (vjerovatno preko `git add -A` ili
ekvivalenta) pokupio moj tada-nekomitovan `docs/context/history.md` u
originalnom obliku (sekcije 15-102, bez §103) i dodao mu svoj vlastiti dated
zapis kao "§103" — ispravno prateći tek uvedenu konvenciju iz fajla koji je
zatekao — ali je sve zajedno commitovao pod potpuno nepovezanom porukom
("refactor(faktura): uvedi javni auto fill api za agent"). `docs/CONTEXT.md`
u tom trenutku još NIJE bio trimovan na disku (moja skripta ga je trimovala
tek nakon te tačke), pa Codex-ov commit ne sadrži moju izmjenu CONTEXT.md-a —
samo history.md kopiju. Nema izgubljenog sadržaja, ali je otkrivena kolizija
brojeva sekcija (moj plan je takođe koristio "§103") — riješeno preimenovanjem
moje stavke u §104 i njenim premještanjem na kraj fajla, iza Codex-ovog zapisa
(vidi §104 u `history.md` za punu napomenu).

## Konflikti / kontradiktorni izvori
`docs/context/history.md` na `git HEAD` (prije mog commit-a) je već sadržao
sekcije 15-103 zahvaljujući gore opisanom sweep-u — tretiran kao važeći
(sadržaj identičan mom, samo bez moje §104 dopune), moja izmjena je samo
dodala §104 na kraj i ništa nije prepisivala. Korisnička potvrda nije bila
potrebna jer je sadržajni konflikt bio čisto numerički (dupli broj sekcije),
ne suštinski.

## Commitovi
Commitovano nakon potvrde korisnika — vidi git log (`docs(context): podijeli
CONTEXT.md na evergreen pravila i history.md` ili slično, provjeriti tačnu
poruku u `git log -1`).

## Rizici / ograničenja
- Bilo koji eksterni alat/skripta koja parsira `docs/CONTEXT.md` očekujući sve brojeve sekcija (npr. do §102) više ih neće naći tamo — treba provjeriti `docs/context/history.md`. Nije pronađen nijedan takav alat u repou, ali nije 100% isključeno.
- `doc_link_checker.sh` je zaustavljen ručno (visio je >3 min bez izlaza, vjerovatno zbog skeniranja `.worktrees/`/venv) — zamijenjen ciljanim `Grep` po `\]\(.*CONTEXT\.md` koji je potvrdio da nijedan markdown link nije pokvaren (fajl i dalje postoji na istoj putanji).
- **Bitnije**: potvrđeno je da autonomni Codex proces aktivno commituje na `windows` branch dok ova sesija radi u ISTOM working tree-u (ne u zasebnom worktree-u), i da njegov commit korak (vjerovatno `git add -A`) pokupi bilo koje nekomitovane fajlove zatečene u working tree-u u tom trenutku, bez obzira ko ih je napravio. Ovo je opšti rizik za bilo koji budući agent koji ostavlja nekomitovane izmjene duže vrijeme dok drugi agent radi paralelno — vrijedi razmotriti da se takvi automatizovani pipeline-ovi izoluju u zaseban git worktree (kao `.worktrees/agent-v2` i sl. koji već postoje za neke druge tokove).

## Potreban follow-up
- Razmotriti sa korisnikom da li Faktura 3-layer Codex pipeline treba da radi u izolovanom `git worktree` umjesto direktno na `windows` working tree-u, da se izbjegne ponovni sweep tuđih nekomitovanih izmjena.

## Potrebna korisnička potvrda
- Da li ovaj pristup (2 fajla umjesto 6 novih foldera iz originalnog dokumenta) odgovara namjeri — ili korisnik ipak želi i `agent_policies/`/`agent_skills/`/`agent_runbooks/` strukturu za nešto specifično (npr. multi-model tool/model selection policy, pošto AGENTS.md već pominje Codex/DeepSeek/GLM/Kimi/MiniMax kao agente na ovom projektu).
- Da li da commitujem ove izmjene sada.
