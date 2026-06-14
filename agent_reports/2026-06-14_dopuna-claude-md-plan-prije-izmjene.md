# Dopuna CLAUDE.md — "Plan prije izmjene" + Status izvora/Konflikti u agent_report

## Datum

2026-06-14

## Agent

Claude Sonnet 4.6 (Claude Code)

## Scope

- `CLAUDE.md` (root) — dvije nove sekcije, bez izmjene postojećeg teksta
  osim ubacivanja

## Status izvora

- Codex-ov prijedlog ("Project room i agent_reports pravila za kompleksne
  zadatke", 15 podsekcija, 8 fajlova po zadatku: `00_task.md`...
  `07_agent_report.md`) — status: razmatran, NIJE direktno primijenjen
- `AGENTS.md` sekcija "Handoff visokog rizika (HIGH/CRITICAL GitNexus
  impact)" sa scope-lock tabelom — status: aktivan, REFERENCIRAN (ne
  dupliran)
- Postojeći `CLAUDE.md` "Format zadatka za agenta" i "OBAVEZNA PROCEDURA →
  Korak 3 — Agent report" — status: aktivan, DOPUNJEN (ne zamijenjen)

## GitNexus impact

`gitnexus_detect_changes(scope="unstaged")` prije commita: `risk_level:
"low"`, `affected_count: 0`, `affected_processes: []`. Čisto dokumentacioni
`.md` fajl — bez funkcionalnog impact-a na kod.

## Šta je urađeno

Dodate dvije nove sekcije u `CLAUDE.md`:

1. Nova sekcija **"Plan prije izmjene — HIGH/CRITICAL GitNexus impact"**
   (između "Format zadatka za agenta" i "OBAVEZNA PROCEDURA"): za simbole
   sa HIGH/CRITICAL `gitnexus_impact`, agent prije izmjene piše JEDAN
   kratki fajl `project_rooms/YYYY-MM-DD_naziv-zadatka.md` sa sekcijama
   Cilj / Pogođeno / Plan / Šta NE dirati / Konflikti. Za MEDIUM ili niži
   impact — preskače se.
2. U "OBAVEZNA PROCEDURA → Korak 3 → Agent report" listi dodate dvije nove
   stavke izvještaja:
   - **Status izvora** (posle Scope) — status ranijih
     agent_reports/memory/kod fajlova korišćenih kao osnova:
     aktivan / zastario / duplikat / treba potvrdu
   - **Konflikti / kontradiktorni izvori** (posle "Pronađeni problemi") —
     ako se dva izvora ne slažu, navesti oba, koji se tretira kao važeći i
     zašto, i DA/NE da li treba korisnička potvrda

## Zašto je urađeno

Korisnik je dobio Codex-ov prijedlog za formalni `project_room` sistem (8
fajlova po kompleksnom zadatku) i tražio moje mišljenje. Moja procjena:
ideja (stani i pripremi kontekst prije rizične izmjene) je korisna, ali
implementacija je predimenzionirana za ovaj solo-projekat — kriterijumi
"kompleksan/rizičan" (MEDIUM+ impact, GUI tok, baza, import/export, mirror
folderi...) su tako široki da bi VEĆINA zadataka iz ove sesije (npr.
border-radius na tab dugmadima, boja Izlaz dugmeta) formalno zahtijevala 8
novih fajlova — birokratija dizajnirana za flotu agenata bez ljudskog
nadzora, dok korisnik ovdje live testira i odlučuje na licu mjesta.

Korisnik je prihvatio "lite" verziju: ugraditi najkorisnije nove elemente
(conflict log, source status, plan prije rizične izmjene) u POSTOJEĆU
strukturu (agent_report template + jedna nova sekcija), umjesto novog
`project_rooms/` foldera sa 8 fajlova po zadatku.

## Kako je urađeno

- Pročitan trenutni `CLAUDE.md` i `AGENTS.md` da se utvrdi šta već postoji
  — `AGENTS.md` već ima "Handoff visokog rizika" sa scope-lock tabelom za
  HIGH/CRITICAL, pa nova sekcija u `CLAUDE.md` na njega REFERENCIRA umjesto
  da duplira format.
- Edit 1: nova sekcija "Plan prije izmjene — HIGH/CRITICAL GitNexus impact"
  ubačena između "Format zadatka za agenta" i "OBAVEZNA PROCEDURA" — logičan
  redoslijed (kako korisnik formuliše zadatak → šta agent radi PRIJE
  rizične izmjene → šta radi POSLIJE svakog zadatka).
- Edit 2: u Korak 3 listi sekcija agent_report-a dodate "Status izvora"
  (odmah posle Scope) i "Konflikti / kontradiktorni izvori" (posle
  "Pronađeni problemi") — obje oznaćene kao "samo za kompleksne/rizične
  zadatke" / "ako postoje", da se ne nameću na sitne fix-ove.

## Šta nije dirano

- `AGENTS.md` — sadrži svoj pred-postojeći necommitovan gitnexus stat-bump
  (39383→41233 simbola) iz ranije sesije, nepovezan s ovim zadatkom;
  ostavljen netaknut, nije ni commitovan ni revertovan.
- `dist_client/CLAUDE.md`, `dist_client/AGENTS.md`, `docs/AGENTS.md`,
  `dist_client/docs/AGENTS.md` — `gitnexus_detect_changes` ih je prikazao
  kao "touched" (indeks-artefakt preklapajućih sekcija), ali `git status`
  potvrđuje da su NETAKNUTI (samo `AGENTS.md` + `CLAUDE.md` su modified).
- Codex-ov originalni prijedlog (8-fajl `project_room` sistem) — NIJE
  implementiran u punom obliku, po korisnikovom izboru "lite" verzije.
- Nikakav `.py`/`.qss`/kod fajl nije mijenjan — čisto dokumentacioni zadatak.

## Verifikacija

- `gitnexus_detect_changes(scope="unstaged")`: `risk_level: "low"`,
  `affected_count: 0`, `affected_processes: []` — potvrđuje da je promjena
  isključivo dokumentaciona.
- `git diff CLAUDE.md` pregledan — dvije nove sekcije ubačene na ispravna
  mjesta, postojeći tekst nepromijenjen osim pred-postojeće gitnexus
  stat-bump linije (39383→41233, automatska, nepovezana).
- IDE markdownlint diagnostics nakon Edit-a: nove sekcije nose
  MD031/MD040 upozorenja (fenced code block bez jezika / bez praznih linija
  oko njega) — ISTI stil kao već postojeći fenced blokovi u istom fajlu
  (npr. originalne linije 25, 30, 40, 115, 123) — fajl već ima desetine
  istih pred-postojećih upozorenja, nije regresija ni novi problem.

## Pronađeni problemi

Nema novih.

## Konflikti / kontradiktorni izvori

Nema. Codex-ov prijedlog i postojeći `CLAUDE.md`/`AGENTS.md` se ne
kontradiktuju — Codex-ov prijedlog je aditivan (nova pravila), a `AGENTS.md`
"Handoff visokog rizika" već djelimično pokriva isti cilj (scope-lock
prijava rizika) drugim formatom — nova sekcija ga referencira da ne nastanu
dva paralelna "izvora istine" za isti koncept.

## Commitovi

| Hash | Poruka |
|------|--------|
| (popunjava se nakon commita) | `docs(agent): dodaj "Plan prije izmjene" i Status izvora/Konflikti u agent_report` |

## Rizici / ograničenja

- Čisto proceduralna/dokumentaciona promjena — nema funkcionalnog rizika za
  aplikaciju.
- Nova pravila trenutno važe samo za `CLAUDE.md` (Claude Code) —
  `AGENTS.md` (Qwen/Copilot/Cursor/drugi agenti) nije dopunjen istim
  pravilima (vidi Potreban follow-up).
- Efikasnost zavisi od toga da agent zaista PREPOZNA kad je
  `gitnexus_impact` HIGH/CRITICAL i kad postoje "kontradiktorni izvori" —
  ovo su smjernice, ne automatska provjera (nema hook/lint koji to forsira).

## Potreban follow-up

- Ako korisnik želi da i ne-Claude agenti (preko `AGENTS.md`, uklj.
  `dist_client/` mirror) prate "Plan prije izmjene" + "Status
  izvora"/"Konflikti" pravila — treba ih dodati i tamo. NIJE urađeno u ovom
  zadatku (korisnikov izbor bio ograničen na CLAUDE.md).
- `project_rooms/` folder još ne postoji — kreira se prvi put kad neki
  zadatak stvarno bude HIGH/CRITICAL impact.

## Potrebna korisnička potvrda

- Pregledati formulacije novih sekcija u `CLAUDE.md` (cca linije 161-186 i
  210-222) i potvrditi da odgovaraju onome što je korisnik imao na umu pod
  "tvoja preporuka".
- Odlučiti da li ova pravila treba proširiti i na `AGENTS.md` za ostale
  agente (vidi Potreban follow-up).
